import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from apps.pets.models import Pet


def private_photo_storage():
    # Deliberately outside MEDIA_ROOT: debug/static media serving must not
    # bypass the authenticated download endpoint.
    return FileSystemStorage(location=settings.PRIVATE_SURRENDER_ROOT)


def photo_path(instance, filename):
    return f"{instance.request_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class SurrenderRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        NEEDS_INFORMATION = "needs_information", "Needs Information"
        WAITLISTED = "waitlisted", "Waitlisted"
        INTAKE_SCHEDULED = "intake_scheduled", "Intake Scheduled"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        RECEIVED = "received", "Received"

    TERMINAL_STATUSES = (Status.DECLINED, Status.CANCELLED, Status.RECEIVED)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="surrender_requests")
    pet_name = models.CharField(max_length=150)
    species = models.CharField(max_length=20, choices=Pet.Species.choices)
    breed = models.CharField(max_length=150, blank=True)
    age_years = models.PositiveSmallIntegerField(default=0)
    age_months = models.PositiveSmallIntegerField(default=0)
    gender = models.CharField(max_length=10, choices=Pet.Gender.choices, default=Pet.Gender.UNKNOWN)
    reason = models.TextField()
    health_information = models.TextField()
    behavior_information = models.TextField()
    contact_number = models.CharField(max_length=30)
    ownership_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    intake_date = models.DateField(null=True, blank=True)
    intake_instructions = models.TextField(blank=True)
    pet = models.OneToOneField(Pet, on_delete=models.PROTECT, null=True, blank=True, related_name="surrender_request")
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="received_surrenders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(age_years__lte=40, age_months__lte=11), name="surrender_valid_age"),
            models.CheckConstraint(condition=models.Q(ownership_confirmed=True), name="surrender_owner_consent"),
            models.CheckConstraint(condition=~models.Q(status="intake_scheduled") | models.Q(intake_date__isnull=False), name="surrender_schedule_has_date"),
            models.CheckConstraint(
                condition=(models.Q(status="received", pet__isnull=False, received_at__isnull=False, received_by__isnull=False)
                           | (~models.Q(status="received") & models.Q(pet__isnull=True, received_at__isnull=True, received_by__isnull=True))),
                name="surrender_received_has_pet",
            ),
        ]


class SurrenderPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(SurrenderRequest, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(storage=private_photo_storage, upload_to=photo_path)


class SurrenderEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(SurrenderRequest, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=40)
    previous_status = models.CharField(max_length=25, blank=True)
    new_status = models.CharField(max_length=25)
    note = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    intake_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
