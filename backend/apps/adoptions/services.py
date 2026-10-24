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
The onsite visit (physical verification, paperwork, payment, handover) happens outside
the system.  PawConnect records the result of that visit, so completion
is an explicit staff action with these side effects:

    AdoptionRecord -> completed
    AdoptionRecord.transaction_id -> generated once and persisted
    AdoptionRecord.completed_at -> timestamp finalized
    AdoptionRecord.completed_date -> date finalized
    Payment.adoption -> linked to the adoption record
    Pet.status -> adopted          (existing business rule: an adopted pet is
                                    never presented as available)
    Application.status -> adoption_completed

Callers and the service both enforce the business rules:
- The application is approved
- The onsite visit date is confirmed
- The required adoption fee (₱500.00) is fully paid through completed payment records
- Concurrency and retries are idempotent and safe
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.notifications.models import create_notification
from apps.payments.constants import PROTOTYPE_ADOPTION_FEE
from apps.payments.models import Payment

from .models import AdoptionRecord, _generate_transaction_id


def is_handover_confirmed(data):
    """Return (True, None) only when the request payload contains an unambiguous
    boolean ``True`` for ``confirmed`` or ``turnover_confirmed``.

    Acceptable:
        {"confirmed": True}
        {"turnover_confirmed": True}
        {"confirmed": True, "turnover_confirmed": True}

    Rejected (returns False + error message):
        {}                                     – field missing
        {"confirmed": False}                   – explicit denial
        {"confirmed": null}                    – null
        {"confirmed": "true"}                  – string, not bool
        {"confirmed": 1}                       – integer, not bool
        {"confirmed": True, "turnover_confirmed": False}  – contradictory
    """
    if not isinstance(data, dict):
        return False, "Invalid request payload format."

    has_confirmed = "confirmed" in data
    has_turnover = "turnover_confirmed" in data

    if not has_confirmed and not has_turnover:
        return False, "Explicit physical handover confirmation is required (confirmed: true)."

    c_val = data.get("confirmed")
    t_val = data.get("turnover_confirmed")

    if has_confirmed and has_turnover:
        # Both provided: both must be exactly boolean True (no contradiction)
        if type(c_val) is bool and c_val is True and type(t_val) is bool and t_val is True:
            return True, None
        return (
            False,
            "Physical turnover confirmation fields must both be boolean true and cannot contradict each other.",
        )

    val = c_val if has_confirmed else t_val
    if type(val) is bool and val is True:
        return True, None

    return False, "Physical turnover must be explicitly confirmed with a boolean value of true."


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


@transaction.atomic
def complete_application_adoption(application, staff_user, notes="", handover_confirmed=None):
    """Finish the adoption for *application* and return its AdoptionRecord.

    Physical Handover Confirmation
    ------------------------------
    Physical turnover must be explicitly confirmed by an authenticated staff member
    with a boolean value of True (handover_confirmed=True). Missing, false, or
    non-boolean values are rejected. The parameter is required on purpose: a
    default of ``True`` would let a future caller complete an adoption without
    deliberately confirming the handover.

    Concurrency & idempotency
    -------------------------
    The Application row is locked with ``select_for_update()`` immediately after
    entering the atomic block.  The locked, reloaded instance is used for all
    subsequent checks so that two simultaneous requests cannot both pass the
    guard and create duplicate records or conflicting state.

    If the adoption was already completed by a concurrent request that won the
    race, the existing AdoptionRecord is returned unchanged — ``transaction_id``,
    ``completed_at``, and staff attribution remain stable.

    Transaction ID
    --------------
    A unique, human-readable ``transaction_id`` is assigned exactly once when
    the adoption is completed and is never regenerated on subsequent retries.
    Uniqueness is enforced at the database level.
    """
    if type(handover_confirmed) is not bool or handover_confirmed is not True:
        raise ValidationError("Physical turnover must be explicitly confirmed with a boolean value of true.")

    from apps.applications.models import Application as ApplicationModel
    from apps.pets.models import Pet

    # ── Acquire row-level lock and reload under the lock ─────────────────────
    app = (
        ApplicationModel.objects.select_for_update()
        .select_related("pet", "adopter")
        .get(id=application.id)
    )

    # ── Idempotent retry: already completed ───────────────────────────────────
    if app.status == "adoption_completed":
        try:
            return app.adoption_record
        except AdoptionRecord.DoesNotExist:
            pass  # edge case: status set but no record yet — fall through

    if app.status != "approved":
        raise ValidationError("Only an approved application can be completed as an adoption.")

    from apps.appointments.eligibility import require_onsite_visit, philippine_today
    appointment = require_onsite_visit(app)

    total_completed = (
        app.payments.filter(status=Payment.Status.COMPLETED).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )
    if total_completed < PROTOTYPE_ADOPTION_FEE:
        raise ValidationError(
            f"The required adoption fee of ₱{PROTOTYPE_ADOPTION_FEE:.2f} has not been fully paid. "
            f"Total completed: ₱{total_completed:.2f}."
        )

    today = philippine_today()
    now = timezone.now()

    # Lock the Pet row as well under the transaction to ensure pet state remains atomic
    pet = Pet.objects.select_for_update().get(id=app.pet_id)

    if pet.status in (Pet.Status.FOR_ASSESSMENT, Pet.Status.UNDER_MEDICAL_CARE):
        raise ValidationError("The pet needs assessment or medical clearance before adoption completion.")

    # ── Create or fetch the AdoptionRecord under a savepoint ─────────────────
    try:
        with transaction.atomic():
            record, created = AdoptionRecord.objects.select_for_update().get_or_create(
                application=app,
                defaults={
                    "pet": pet,
                    "adopter": app.adopter,
                    "staff_member": staff_user,
                    "appointment": appointment,
                    "adoption_date": appointment.requested_date if appointment else today,
                    "notes": notes,
                },
            )
    except IntegrityError:
        record = AdoptionRecord.objects.select_for_update().get(application=app)
        created = False

    # Idempotent retry: already completed under the lock, return unchanged
    if not created and record.status == AdoptionRecord.Status.COMPLETED:
        return record
    if not created and record.status in (AdoptionRecord.Status.CANCELLED, AdoptionRecord.Status.RETURNED):
        raise ValidationError("A closed adoption record cannot be completed.")

    previous_record_status = record.status

    if not created and notes:
        record.notes = f"{record.notes}\n{notes}".strip() if record.notes else notes

    record.status = AdoptionRecord.Status.COMPLETED
    record.completed_date = today
    if not record.completed_at:
        record.completed_at = now
    record.staff_member = staff_user
    if not record.appointment and appointment:
        record.appointment = appointment
    if record.adoption_date is None:
        record.adoption_date = appointment.requested_date if appointment else today

    # Generate unique transaction ID if not already assigned
    if not record.transaction_id:
        for _ in range(5):
            candidate = _generate_transaction_id()
            if not AdoptionRecord.objects.filter(transaction_id=candidate).exists():
                record.transaction_id = candidate
                break
        else:
            raise IntegrityError(
                "Could not generate a unique transaction_id after 5 attempts."
            )

    record.save()

    # Attach the recorded onsite payment(s) to the adoption record so the
    # completed adoption keeps its payment history.
    app.payments.filter(adoption__isnull=True).update(adoption=record)

    pet = app.pet
    if pet.status != "adopted":
        pet.status = "adopted"
        pet.save(update_fields=["status"])

    app.status = "adoption_completed"
    app.save(update_fields=["status"])
    from apps.appointments.services import close_pending_reschedules
    close_pending_reschedules(app, staff_user, "Adoption completed at the confirmed visit.")

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
        object_id=str(app.id),
        previous_value="approved",
        new_value="adoption_completed",
    )
    create_notification(
        user=app.adopter,
        title="Adoption Completed",
        message=(
            f"Congratulations! Your adoption of {app.pet.name} is now complete."
        ),
        notification_type="adoption",
        link=f"/applications/{app.id}",
    )
    return record


@transaction.atomic
def cancel_scheduled_adoption(record, staff, reason, confirmed):
    """Close a scheduled adoption, preserving payments and every historical row."""
    from apps.applications.models import Application
    from apps.appointments.models import Appointment
    from apps.appointments.services import (
        audit, notify_adopter, require_confirmation, require_staff, required_reason, close_pending_reschedules,
    )
    from apps.pets.models import Pet

    require_staff(staff)
    require_confirmation(confirmed)
    reason = required_reason(reason)
    application = Application.objects.select_for_update().get(pk=record.application_id)
    pet = Pet.objects.select_for_update().get(pk=application.pet_id)
    record = AdoptionRecord.objects.select_for_update().get(pk=record.pk)
    if record.status == AdoptionRecord.Status.CANCELLED:
        return record  # Retry preserves the original reason, timestamp and audit.
    if record.status != AdoptionRecord.Status.SCHEDULED:
        raise ValidationError("Only a Scheduled adoption may be cancelled. Completed adoptions cannot be cancelled.")
    if not application.can_transition_to(Application.Status.CANCELLED):
        raise ValidationError("This application cannot be cancelled in its current state.")
    previous_app_status = application.status
    now = timezone.now()
    record.status = AdoptionRecord.Status.CANCELLED
    record.cancellation_reason = reason
    record.cancelled_at = now
    record.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])
    application.status = Application.Status.CANCELLED
    application.save(update_fields=["status", "updated_at"])
    audit(staff, "adoption_cancelled", record, "scheduled", f"cancelled: {reason}")
    audit(staff, "status_change", application, previous_app_status, "cancelled")
    for appointment in application.appointments.select_for_update().filter(status__in=Appointment.ACTIVE_STATUSES):
        previous = appointment.status
        appointment.status = Appointment.Status.CANCELLED
        appointment.reviewed_by = staff
        appointment.reviewed_at = now
        appointment.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        audit(staff, "appointment_cancelled", appointment, previous, f"cancelled: {reason}")
    close_pending_reschedules(application, staff, f"Adoption cancelled: {reason}")
    other_reservations = (
        Application.objects.filter(pet=pet, status=Application.Status.APPROVED).exclude(pk=application.pk).exists()
        or AdoptionRecord.objects.filter(pet=pet, status__in=["scheduled", "completed"]).exclude(pk=record.pk).exists()
    )
    if not other_reservations and pet.status in (Pet.Status.PENDING, Pet.Status.RESERVED):
        previous = pet.status
        pet.status = Pet.Status.AVAILABLE
        pet.save(update_fields=["status", "updated_at"])
        audit(staff, "status_change", pet, previous, "available")
    notify_adopter(application, "Adoption Cancelled", (
        f"Your adoption of {pet.name} has been cancelled. Reason: {reason}. "
        "Existing payment records have been retained; cancellation does not automatically issue a refund."
    ), notification_type="adoption")
    return record


@transaction.atomic
def return_completed_adoption(record, staff, reason, confirmed):
    """Record physical return once, preserving completion and payment history."""
    from zoneinfo import ZoneInfo

    from apps.applications.models import Application
    from apps.appointments.services import audit, notify_adopter, require_staff, required_reason
    from apps.pets.models import Pet

    require_staff(staff)
    if confirmed is not True:
        raise ValidationError("Confirm that the pet has been physically returned to the shelter (confirmed: true).")
    reason = required_reason(reason)
    # Match completion/cancellation lock order; all side effects commit together.
    application = Application.objects.select_for_update().get(pk=record.application_id)
    pet = Pet.objects.select_for_update().get(pk=application.pet_id)
    record = AdoptionRecord.objects.select_for_update().get(pk=record.pk)
    if record.status == AdoptionRecord.Status.RETURNED:
        # A retry must never release a pet that has since been adopted again.
        return record
    if not record.can_transition_to(AdoptionRecord.Status.RETURNED):
        raise ValidationError("Only a Completed adoption may be marked as Returned.")
    if (
        Application.objects.filter(pet=pet, status=Application.Status.APPROVED).exclude(pk=application.pk).exists()
        or AdoptionRecord.objects.filter(pet=pet, status__in=["scheduled", "completed"]).exclude(pk=record.pk).exists()
    ):
        raise ValidationError("This pet has another active adoption. Resolve it before recording this return.")

    now = timezone.now()
    record.status = AdoptionRecord.Status.RETURNED
    record.return_reason = reason
    record.return_date = timezone.localtime(now, ZoneInfo("Asia/Manila")).date()
    record.returned_at = now
    record.save(update_fields=["status", "return_reason", "return_date", "returned_at", "updated_at"])
    previous_pet_status = pet.status
    if pet.status != Pet.Status.FOR_ASSESSMENT:
        pet.status = Pet.Status.FOR_ASSESSMENT
        pet.save(update_fields=["status", "updated_at"])
        audit(staff, "status_change", pet, previous_pet_status, Pet.Status.FOR_ASSESSMENT)
    audit(staff, "adoption_returned", record, "completed", f"returned: {reason}")
    notify_adopter(application, "Adoption Returned", (
        f"The shelter has received {pet.name} back and recorded your adoption as Returned. "
        f"Reason: {reason}. The pet is For Assessment before being offered for adoption again. "
        "Existing payment records and receipts are retained; no automatic refund is issued."
    ), notification_type="adoption")
    return record
