from django.db import models


class Report(models.Model):
    """Report metadata. Report data is computed dynamically."""

    class Type(models.TextChoices):
        ADOPTION = "adoption", "Adoption Report"
        PET_INVENTORY = "pet_inventory", "Pet Inventory Report"
        ADOPTER = "adopter", "Adopter Report"
        APPLICATION = "application", "Application Report"
        HEALTH = "health", "Health Record Report"
        PAYMENT = "payment", "Payment Report"

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=Type.choices)
    parameters = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="reports_generated"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.report_type}: {self.name}"