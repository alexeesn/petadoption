"""Appointment follow-up decisions, serialized on the same application lock as turnover/payment."""
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.notifications.models import create_notification
from .models import Appointment, RescheduleRequest, CENTER_CLOSING_TIME, validate_visit_date


def require_staff(user):
    if not user or not (user.is_staff_role or user.is_admin_role):
        raise PermissionDenied("Only staff or administrators may make this decision.")


def require_confirmation(confirmed):
    if confirmed is not True:
        raise ValidationError("Explicit confirmation is required (confirmed: true).")


def required_reason(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A reason is required.")
    if len(reason.strip()) > 2000:
        raise ValidationError("Reason must be 2000 characters or fewer.")
    return reason.strip()


def ensure_open_application(application):
    from apps.adoptions.models import AdoptionRecord
    if application.status != Application.Status.APPROVED:
        raise ValidationError("The adoption application is no longer approved for scheduling.")
    if AdoptionRecord.objects.filter(application=application).exclude(status="scheduled").exists():
        raise ValidationError("This adoption record is closed and cannot be rescheduled.")


def audit(user, action, obj, previous, new):
    AuditLog.objects.create(
        user=user, action=action, model_name=type(obj).__name__, object_id=str(obj.pk),
        previous_value=previous, new_value=new,
    )


def notify_adopter(application, title, message, notification_type="appointment"):
    create_notification(
        user=application.adopter, title=title, message=message,
        notification_type=notification_type, link=f"/applications/{application.pk}",
    )
    # Do not send an email for a decision that is subsequently rolled back.
    from .emails import send_followup_email
    transaction.on_commit(lambda: send_followup_email(application, title, message))


def visit_has_ended(appointment):
    # Center hours are in the Philippines, independent of the server's timezone.
    now = timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila"))
    return appointment.requested_date < now.date() or (
        appointment.requested_date == now.date() and now.time() >= CENTER_CLOSING_TIME
    )


def validate_reschedule_date(value):
    validate_visit_date(value)
    if value < timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date():
        raise ValidationError("The new visit date cannot be in the past in Philippine time.")


def close_pending_reschedules(application, staff, note):
    """Called under the application's lock when an adoption becomes terminal."""
    for request in application.reschedule_requests.select_for_update().filter(status=RescheduleRequest.Status.PENDING):
        request.status = RescheduleRequest.Status.CANCELLED
        request.decision_note = note
        request.reviewed_by = staff
        request.reviewed_at = timezone.now()
        request.save(update_fields=["status", "decision_note", "reviewed_by", "reviewed_at"])
        audit(staff, "reschedule_cancelled", request, "pending", note)


@transaction.atomic
def mark_no_show(appointment, staff, reason, confirmed):
    require_staff(staff)
    require_confirmation(confirmed)
    reason = required_reason(reason)
    application = Application.objects.select_for_update().get(pk=appointment.application_id)
    ensure_open_application(application)
    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
    if appointment.status != Appointment.Status.CONFIRMED:
        raise ValidationError("Only a confirmed appointment can be marked as a no-show.")
    if not visit_has_ended(appointment):
        raise ValidationError("The visit date must have ended before recording a no-show (after 5 PM Philippine time).")
    appointment.status = Appointment.Status.NO_SHOW
    appointment.no_show_reason = reason
    appointment.reviewed_by = staff
    appointment.reviewed_at = timezone.now()
    appointment.save(update_fields=["status", "no_show_reason", "reviewed_by", "reviewed_at", "updated_at"])
    audit(staff, "appointment_no_show", appointment, "confirmed", f"no_show: {reason}")
    notify_adopter(application, "Visit Marked as No-show", (
        f"Your visit for {appointment.pet.name} on {appointment.requested_date} was marked as a no-show. "
        f"Reason: {reason}. Your adoption has not been cancelled. You may request a new date in your application."
    ))
    return appointment


@transaction.atomic
def request_reschedule(appointment, adopter, requested_date, reason):
    application = Application.objects.select_for_update().get(pk=appointment.application_id)
    if not adopter.is_adopter or application.adopter_id != adopter.pk:
        raise PermissionDenied("Only the application owner can request a new date.")
    ensure_open_application(application)
    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
    if appointment.status not in (Appointment.Status.CONFIRMED, Appointment.Status.NO_SHOW):
        raise ValidationError("Only a confirmed or no-show appointment can be rescheduled.")
    validate_reschedule_date(requested_date)
    if requested_date == appointment.requested_date:
        raise ValidationError("Choose a date different from the original appointment.")
    reason = required_reason(reason)
    if application.appointments.filter(status__in=Appointment.ACTIVE_STATUSES).exclude(pk=appointment.pk).exists():
        raise ValidationError("This application already has a newer active appointment.")
    if application.reschedule_requests.filter(status=RescheduleRequest.Status.PENDING).exists():
        raise ValidationError("This application already has a pending reschedule request.")
    request = RescheduleRequest.objects.create(
        application=application, appointment=appointment, original_date=appointment.requested_date,
        requested_date=requested_date, reason=reason,
    )
    audit(adopter, "reschedule_requested", request, "", f"{appointment.requested_date} -> {requested_date}: {reason}")
    for staff in User.objects.filter(role__in=["staff", "admin"], is_active=True):
        create_notification(
            user=staff, title="Reschedule Requested",
            message=(f"{adopter.email} requests a new visit date for {appointment.pet.name}: "
                     f"{appointment.requested_date} to {requested_date}. Reason: {reason}"),
            notification_type="appointment", link="/appointments?tab=reschedules",
        )
    return request


@transaction.atomic
def review_reschedule(request, staff, approve, reason, confirmed):
    require_staff(staff)
    require_confirmation(confirmed)
    application = Application.objects.select_for_update().get(pk=request.application_id)
    ensure_open_application(application)
    request = RescheduleRequest.objects.select_for_update().get(pk=request.pk)
    if request.status != RescheduleRequest.Status.PENDING:
        raise ValidationError("This reschedule request has already been decided.")
    appointment = Appointment.objects.select_for_update().get(pk=request.appointment_id)
    if appointment.status not in (Appointment.Status.CONFIRMED, Appointment.Status.NO_SHOW):
        raise ValidationError("The original appointment is no longer eligible for rescheduling.")
    if application.appointments.filter(status__in=Appointment.ACTIVE_STATUSES).exclude(pk=appointment.pk).exists():
        raise ValidationError("This application already has another active appointment.")
    if approve:
        # Revalidate at decision time: a proposed date can expire while pending.
        validate_reschedule_date(request.requested_date)
        if appointment.status == Appointment.Status.CONFIRMED:
            appointment.status = Appointment.Status.RESCHEDULED
            appointment.save(update_fields=["status", "updated_at"])
            audit(staff, "appointment_rescheduled", appointment, "confirmed", "rescheduled")
        replacement = Appointment.objects.create(
            application=application, adopter=application.adopter, pet=application.pet,
            requested_date=request.requested_date, status=Appointment.Status.CONFIRMED,
            reviewed_by=staff, reviewed_at=timezone.now(),
        )
        audit(staff, "appointment_confirmed", replacement, "", "confirmed (reschedule)")
        from apps.adoptions.services import schedule_adoption_record_for_appointment
        schedule_adoption_record_for_appointment(replacement, staff)
        request.replacement_appointment = replacement
        request.status = RescheduleRequest.Status.APPROVED
        request.decision_note = "New visit date approved."
        title = "Reschedule Approved"
        message = f"Your visit for {application.pet.name} was moved from {request.original_date} to {request.requested_date}."
    else:
        request.decision_note = required_reason(reason)
        request.status = RescheduleRequest.Status.REJECTED
        title = "Reschedule Not Approved"
        message = (f"Your requested visit date {request.requested_date} for {application.pet.name} was not approved. "
                   f"Reason: {request.decision_note}. The original appointment remains {appointment.get_status_display()}. "
                   "You may submit another reschedule request.")
    request.reviewed_by = staff
    request.reviewed_at = timezone.now()
    request.save(update_fields=["status", "decision_note", "reviewed_by", "reviewed_at", "replacement_appointment"])
    audit(staff, "reschedule_reviewed", request, "pending", f"{request.status}: {request.decision_note}")
    notify_adopter(application, title, message)
    return request
