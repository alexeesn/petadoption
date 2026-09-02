import uuid
from django.db import models
from django.conf import settings


class Review(models.Model):
    """Staff review of an application."""

    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        REQUEST_INFO = "request_info", "Request Additional Information"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reviews_made"
    )
    decision = models.CharField(max_length=20, choices=Decision.choices)
    internal_notes = models.TextField(blank=True, help_text="Internal notes - NEVER visible to adopter")
    adopter_visible_notes = models.TextField(blank=True, help_text="Notes visible to adopter")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review by {self.reviewer} on app {self.application_id}: {self.decision}"