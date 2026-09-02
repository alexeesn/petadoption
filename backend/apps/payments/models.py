import uuid
from django.db import models
from django.conf import settings


class Payment(models.Model):
    """Payment records. Payment is OPTIONAL - free adoptions need no payment."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        GCASH = "gcash", "GCash"
        PAYMAYA = "paymaya", "PayMaya"
        CREDIT_CARD = "credit_card", "Credit Card"
        ONLINE = "online", "Online"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="payments"
    )
    adoption = models.ForeignKey(
        "adoptions.AdoptionRecord", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments"
    )
    package = models.ForeignKey(
        "packages.AdoptionPackage", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    receipt_number = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments_processed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id}: ₱{self.amount} ({self.status})"

    @property
    def is_free(self):
        return self.amount == 0

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.amount == 0 and self.status == "pending":
            # Free adoptions don't need payment tracking
            pass