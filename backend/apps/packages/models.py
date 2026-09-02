import uuid
from django.db import models


class AdoptionPackage(models.Model):
    """Optional adoption package with inclusions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    inclusions = models.JSONField(default=list, blank=True, help_text="List of inclusions")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Adoption Package"
        verbose_name_plural = "Adoption Packages"
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} - ₱{self.price}"