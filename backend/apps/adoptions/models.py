import secrets
import uuid
from django.db import models
from django.conf import settings


def _generate_transaction_id():
    """Generate a stable unique transaction ID.

    Format: TXN-<12 uppercase hex chars>
    Example: TXN-4A2F8B1C9D0E

    Generated once when an adoption is finalized and stored permanently.
    """
    return "TXN-" + secrets.token_hex(6).upper()


class AdoptionRecord(models.Model):
    """Adoption records, scheduled and completed by the onsite visit workflow.

    A record is created automatically by the backend when staff confirm the
    adopter's onsite visit date (see
    ``apps.adoptions.services.schedule_adoption_record_for_appointment``), so
    staff never create a Scheduled record by hand:

        application approved
        -> adopter picks a visit date (appointment pending_confirmation)
        -> staff confirm the date (appointment confirmed)
        -> AdoptionRecord auto-created/updated with status "scheduled"
        -> staff record the onsite payment
        -> staff complete the adoption (AdoptionRecord "completed")

    When the record moves to "completed", ``transaction_id`` is populated with
    a stable unique reference code that identifies the completed transaction.
    It is generated once, persisted immediately, and never regenerated on view,
    refresh, or export.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    VALID_TRANSITIONS = {
        "scheduled": ["completed", "cancelled"],
        "completed": ["returned"],
        "cancelled": [],
        "returned": [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "applications.Application", on_delete=models.CASCADE, related_name="adoption_record"
    )
    pet = models.ForeignKey("pets.Pet", on_delete=models.CASCADE, related_name="adoption_records")
    adopter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="adoption_records")
    staff_member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="adoptions_handled"
    )
    # The approved onsite visit that scheduled this adoption.  Optional so
    # records created before this field existed (and records completed straight
    # from an application without a stored appointment) stay valid.
    appointment = models.ForeignKey(
        "appointments.Appointment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="adoption_records",
        help_text="Confirmed onsite visit this adoption record was scheduled from",
    )
    # Human-readable unique transaction ID for completed adoptions.
    # Populated when status transitions to "completed"; NULL for scheduled /
    # cancelled records that have not yet been released.  Enforced unique at
    # the DB level so no two completed transactions share an ID.
    transaction_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        help_text=(
            "Stable unique reference code for the completed adoption transaction. "
            "Generated once when the adoption is completed and never changed."
        ),
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    adoption_date = models.DateField(blank=True, null=True)
    completed_date = models.DateField(blank=True, null=True)
    completed_at = models.DateTimeField(
        blank=True, null=True,
        help_text="Timestamp when the adoption transaction was finalized.",
    )
    notes = models.TextField(blank=True)
    return_reason = models.TextField(blank=True)
    # Retain the lifecycle columns already present in deployed databases.
    # In particular, cancellation_reason is NOT NULL: inserts must supply
    # Django's empty-string default even when merely scheduling an adoption.
    cancellation_reason = models.TextField(
        blank=True, help_text="Why the scheduled adoption was cancelled (recorded by staff)"
    )
    cancelled_at = models.DateTimeField(
        blank=True, null=True, help_text="When the adoption was cancelled"
    )
    return_date = models.DateField(
        blank=True, null=True, help_text="Date the pet was actually returned"
    )
    returned_at = models.DateTimeField(
        blank=True, null=True, help_text="When the completed adoption was recorded as returned"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Adoption Record"
        verbose_name_plural = "Adoption Records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Adoption: {self.adopter.email} -> {self.pet.name}"

    def can_transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed
