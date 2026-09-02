import uuid
from django.db import models
from django.conf import settings


class AdoptionRecord(models.Model):
    """Records of completed or in-progress adoptions."""

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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    adoption_date = models.DateField(blank=True, null=True)
    completed_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)
    return_reason = models.TextField(blank=True)
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