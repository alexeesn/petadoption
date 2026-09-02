import uuid
from django.db import models


class HealthRecord(models.Model):
    """Health records for pets - Staff/Admin only."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey("pets.Pet", on_delete=models.CASCADE, related_name="health_records")
    veterinarian_name = models.CharField(max_length=200, blank=True)
    veterinary_clinic = models.CharField(max_length=200, blank=True)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    record_date = models.DateField()
    next_checkup_date = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="health_records_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Health Record"
        verbose_name_plural = "Health Records"
        ordering = ["-record_date"]

    def __str__(self):
        return f"Health record for {self.pet.name} on {self.record_date}"


class Vaccination(models.Model):
    """Vaccination records for pets."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey("pets.Pet", on_delete=models.CASCADE, related_name="vaccinations")
    vaccine_name = models.CharField(max_length=200)
    date_administered = models.DateField()
    next_due_date = models.DateField(blank=True, null=True)
    veterinarian = models.CharField(max_length=200, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vaccination"
        verbose_name_plural = "Vaccinations"
        ordering = ["-date_administered"]

    def __str__(self):
        return f"{self.vaccine_name} for {self.pet.name}"

    @property
    def is_due(self):
        """Check if vaccination is due (past next_due_date)."""
        if not self.next_due_date:
            return False
        from django.utils import timezone
        return timezone.now().date() > self.next_due_date

    @property
    def vaccination_status(self):
        """Computed vaccination status."""
        if not self.next_due_date:
            return "up_to_date"
        from django.utils import timezone
        today = timezone.now().date()
        if today > self.next_due_date:
            return "overdue"
        from datetime import timedelta
        if (self.next_due_date - today) <= timedelta(days=30):
            return "due_soon"
        return "up_to_date"