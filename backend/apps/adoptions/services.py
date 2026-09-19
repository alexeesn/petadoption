"""
Adoption scheduling and completion.

Scheduling
----------
Confirming the onsite visit date (an appointment decision made by staff) is
what puts an adoption on the calendar, so the backend creates/updates the
AdoptionRecord itself:

    appointment confirmed -> AdoptionRecord (status "scheduled")

``schedule_adoption_record_for_appointment`` is called by the appointment
approve action; it is idempotent, so repeated/retried approvals reuse the one
record that belongs to the application.

Completion
----------
The onsite visit (physical verification, paperwork, payment) happens outside
the system.  PawConnect only records the result of that visit, so completion
is a single, explicit staff action with these side effects:

    AdoptionRecord -> completed
    Payment.adoption -> linked to the adoption record
    Pet.status -> adopted          (existing business rule: an adopted pet is
                                    never presented as available)
    Application.status -> adoption_completed

Callers must validate the business rules *before* calling this helper (the
application is approved, the onsite visit date is confirmed and the onsite
payment has been recorded).  The API view owns those checks; keeping the side
effects here means there is one place that finishes an adoption.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.notifications.models import create_notification

from .models import AdoptionRecord


def schedule_adoption_record_for_appointment(appointment, staff_user=None):
    """Create or update the AdoptionRecord for a *confirmed* onsite visit.

    Confirming the requested visit date is the moment an adoption becomes
    scheduled, so the backend performs that scheduling itself: staff never
    create a Scheduled AdoptionRecord by hand (see the appointment approve
    action in ``apps.appointments.views``).

    Idempotent by design:

    * ``AdoptionRecord.application`` is a OneToOneField, so there is at most
      one record per adoption transaction.  ``get_or_create`` reuses an
      existing row instead of creating a second one when staff approve the
      appointment again, a request is retried, or the frontend submits the
      approval twice.
    * A record that already reached a terminal/re-entry state (completed,
      cancelled, returned) is returned untouched, so approving a date can
      never reopen or duplicate finished history.

    Returns the AdoptionRecord, or ``None`` when the appointment/application
    state does not allow scheduling (not confirmed, application not approved).
    """
    from apps.applications.models import Application
    from apps.appointments.models import Appointment

    application = appointment.application

    # Guard the invalid states: only a confirmed appointment on an *approved*
    # application may produce a Scheduled adoption record.
    if appointment.status != Appointment.Status.CONFIRMED:
        return None
    if application.status != Application.Status.APPROVED:
        return None

    defaults = {
        "pet": application.pet,
        "adopter": application.adopter,
        "appointment": appointment,
        "staff_member": staff_user,
        "adoption_date": appointment.requested_date,
    }
    try:
        # Inner atomic block: if a concurrent approval wins the OneToOne
        # race the savepoint is rolled back and the existing row is fetched
        # instead of raising for the caller.
        with transaction.atomic():
            record, created = AdoptionRecord.objects.get_or_create(
                application=application, defaults=defaults
            )
    except IntegrityError:
        record = AdoptionRecord.objects.get(application=application)
        created = False

    if not created and record.status != AdoptionRecord.Status.SCHEDULED:
        # Completed / cancelled / returned history is preserved as-is.
        return record

    if not created:
        # Same record, fresh scheduling data from the newly confirmed date.
        record.pet = application.pet
        record.adopter = application.adopter
        record.appointment = appointment
        record.adoption_date = appointment.requested_date
        if staff_user is not None:
            record.staff_member = staff_user
        record.save(
            update_fields=[
                "pet", "adopter", "appointment", "adoption_date",
                "staff_member", "updated_at",
            ]
        )

    AuditLog.objects.create(
        user=staff_user,
        action="adoption_scheduled",
        model_name="AdoptionRecord",
        object_id=str(record.id),
        previous_value="" if created else AdoptionRecord.Status.SCHEDULED,
        new_value=f"{AdoptionRecord.Status.SCHEDULED} (appointment {appointment.id})",
    )
    return record


def complete_application_adoption(application, staff_user, notes=""):
    """Finish the adoption for *application* and return its AdoptionRecord."""
    appointment = (
        application.appointments.filter(status="confirmed")
        .order_by("-requested_date")
        .first()
    )
    today = timezone.localdate()

    record, created = AdoptionRecord.objects.get_or_create(
        application=application,
        defaults={
            "pet": application.pet,
            "adopter": application.adopter,
            "staff_member": staff_user,
            "adoption_date": appointment.requested_date if appointment else today,
            "notes": notes,
        },
    )
    previous_record_status = record.status

    if not created and notes:
        record.notes = f"{record.notes}\n{notes}".strip() if record.notes else notes

    record.status = AdoptionRecord.Status.COMPLETED
    record.completed_date = today
    record.staff_member = staff_user
    if record.adoption_date is None:
        record.adoption_date = appointment.requested_date if appointment else today
    record.save()

    # Attach the recorded onsite payment(s) to the adoption record so the
    # completed adoption keeps its payment history.
    application.payments.filter(adoption__isnull=True).update(adoption=record)

    pet = application.pet
    if pet.status != "adopted":
        pet.status = "adopted"
        pet.save(update_fields=["status"])

    application.status = "adoption_completed"
    application.save(update_fields=["status"])

    AuditLog.objects.create(
        user=staff_user,
        action="adoption_completed",
        model_name="AdoptionRecord",
        object_id=str(record.id),
        previous_value=previous_record_status,
        new_value=AdoptionRecord.Status.COMPLETED,
    )
    AuditLog.objects.create(
        user=staff_user,
        action="status_change",
        model_name="Application",
        object_id=str(application.id),
        previous_value="approved",
        new_value="adoption_completed",
    )
    create_notification(
        user=application.adopter,
        title="Adoption Completed",
        message=(
            f"Congratulations! Your adoption of {application.pet.name} is now complete."
        ),
        notification_type="adoption",
        link=f"/applications/{application.id}",
    )
    return record
