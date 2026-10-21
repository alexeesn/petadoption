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
def complete_application_adoption(application, staff_user, notes=""):
    """Finish the adoption for *application* and return its AdoptionRecord.

    Transaction ID
    --------------
    A unique, human-readable ``transaction_id`` is assigned exactly once when
    the adoption is completed.  If the record was already completed (idempotent
    retry), the existing record and its ``transaction_id`` are returned unchanged.
    Uniqueness is enforced at the database level.
    """
    # Idempotent retry: already completed, return unchanged
    if application.status == "adoption_completed" and hasattr(application, "adoption_record"):
        return application.adoption_record

    if application.status != "approved":
        raise ValidationError("Only an approved application can be completed as an adoption.")

    appointment = (
        application.appointments.filter(status="confirmed")
        .order_by("-requested_date")
        .first()
    )
    if not appointment:
        raise ValidationError(
            "The onsite visit date must be confirmed before turnover can be completed."
        )

    total_completed = (
        application.payments.filter(status=Payment.Status.COMPLETED).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )
    if total_completed < PROTOTYPE_ADOPTION_FEE:
        raise ValidationError(
            f"The required adoption fee of ₱{PROTOTYPE_ADOPTION_FEE:.2f} has not been fully paid. "
            f"Total completed: ₱{total_completed:.2f}."
        )

    today = timezone.localdate()
    now = timezone.now()

    record, created = AdoptionRecord.objects.get_or_create(
        application=application,
        defaults={
            "pet": application.pet,
            "adopter": application.adopter,
            "staff_member": staff_user,
            "appointment": appointment,
            "adoption_date": appointment.requested_date if appointment else today,
            "notes": notes,
        },
    )

    # Idempotent retry: already completed, return unchanged
    if not created and record.status == AdoptionRecord.Status.COMPLETED:
        return record

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
