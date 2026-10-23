"""
Onsite visit appointment scheduling.

The adoption workflow treats the appointment date decision as a *separate*
decision from the adoption application decision:

    application approved
    -> adopter picks an onsite visit date (pending_confirmation)
    -> staff/admin confirms the date (confirmed) or rejects it with a reason
       (rejected)

Approving an adoption application never creates an appointment — the adopter
always chooses the date themselves from the adopter portal.

Reschedule requests retain the original appointment until staff approve a
confirmed replacement; no-show, rescheduled and cancelled visits stay in history.

Center operating schedule: Monday-Saturday, 8:00 AM-5:00 PM.
"""
import uuid
from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Center operating schedule.  Monday is 0 and Sunday is 6 (date.weekday()).
CENTER_VISIT_WEEKDAYS = frozenset({0, 1, 2, 3, 4, 5})
CENTER_OPENING_TIME = time(8, 0)
CENTER_CLOSING_TIME = time(17, 0)

# The center is also closed on holidays and work suspensions.  This project has
# NO holiday / work-suspension data source (no model, API, or imported
# calendar), so nothing can be listed here yet and the set is intentionally
# empty: the system cannot detect holidays on its own.  Dates added to this set
# are refused by the same validation path as Sundays and past dates, so
# wiring a real source later means populating this set (or replacing
# CenterSchedule.is_open_on) and nothing else.
CENTER_CLOSED_DATES = frozenset()


class CenterSchedule:
    """Selectable onsite visit dates for the center."""

    @staticmethod
    def is_open_on(visit_date):
        """True when *visit_date* is a date the center accepts visits on."""
        if visit_date is None:
            return False
        if visit_date.weekday() not in CENTER_VISIT_WEEKDAYS:
            return False
        if visit_date in CENTER_CLOSED_DATES:
            return False
        return True

    @staticmethod
    def describe():
        """Human-readable summary of the operating schedule."""
        return "Monday-Saturday, 8:00 AM-5:00 PM"


def validate_visit_date(value):
    """Validate a requested onsite visit date (used by API and Django admin)."""
    if value is None:
        raise ValidationError("An appointment date is required.")
    if value < timezone.localdate():
        raise ValidationError("Appointment date cannot be in the past.")
    if value.weekday() not in CENTER_VISIT_WEEKDAYS:
        raise ValidationError(
            "The center only accepts visits Monday to Saturday. "
            "Please choose a date when the center is open."
        )
    if value in CENTER_CLOSED_DATES:
        raise ValidationError(
            "The center is closed on that date (holiday or work suspension). "
            "Please choose another date."
        )


class Appointment(models.Model):
    """An adopter's requested onsite visit date, reviewed by staff/admin."""

    class Status(models.TextChoices):
        PENDING_CONFIRMATION = "pending_confirmation", "Pending Confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        NO_SHOW = "no_show", "No-show"
        RESCHEDULED = "rescheduled", "Rescheduled"
        CANCELLED = "cancelled", "Cancelled"

    # Only these statuses block a new request for the same application.
    ACTIVE_STATUSES = (Status.PENDING_CONFIRMATION, Status.CONFIRMED)

    VALID_TRANSITIONS = {
        "pending_confirmation": ["confirmed", "rejected", "cancelled"],
        "confirmed": ["no_show", "rescheduled", "cancelled"],
        "no_show": [],
        "rescheduled": [],
        "cancelled": [],
        "rejected": [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="appointments"
    )
    # Derived server-side from the application so an appointment can never be
    # attached to the wrong adopter or pet.
    adopter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments"
    )
    pet = models.ForeignKey("pets.Pet", on_delete=models.CASCADE, related_name="appointments")
    requested_date = models.DateField(validators=[validate_visit_date])
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING_CONFIRMATION
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_appointments"
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(
        blank=True, help_text="Why the requested date was rejected - visible to the adopter"
    )
    # Keep the existing database column in the model so fresh requests supply
    # its empty-string default instead of inserting NULL into a required field.
    no_show_reason = models.TextField(
        blank=True,
        help_text=(
            "Staff note recorded when the adopter did not show up for a confirmed "
            "visit. The adoption is not cancelled by a no-show alone."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        ordering = ["-created_at"]
        constraints = [
            # A rejected/cancelled request is history; only one *active*
            # (pending_confirmation or confirmed) request may exist per
            # application (AGENTS.md business rule: no duplicate active
            # appointment requests).
            models.UniqueConstraint(
                fields=["application"],
                condition=models.Q(status__in=["pending_confirmation", "confirmed"]),
                name="unique_active_appointment_per_application",
            )
        ]

    def __str__(self):
        return f"Appointment {self.application_id} on {self.requested_date} ({self.status})"

    def can_transition_to(self, new_status):
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def clean(self):
        # Also validates dates created through Django admin / shell.
        validate_visit_date(self.requested_date)


class RescheduleRequest(models.Model):
    """An adopter's proposed date. The original appointment stays unchanged until approved."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="reschedule_requests"
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.PROTECT, related_name="reschedule_requests"
    )
    original_date = models.DateField()
    requested_date = models.DateField(validators=[validate_visit_date])
    reason = models.TextField(max_length=2000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_reschedules",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    replacement_appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_reschedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["application"], condition=models.Q(status="pending"),
                name="unique_pending_reschedule_per_application",
            ),
        ]
