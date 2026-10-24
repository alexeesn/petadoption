import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# A shelter pet is never realistically older than this; used to validate the
# staff-entered age (in years) on the model and through the API serializer.
MAX_PET_AGE_YEARS = 40
MAX_PET_AGE_MONTHS = 11


class Pet(models.Model):
    """Pet available for adoption."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        PENDING = "pending", "Pending"
        RESERVED = "reserved", "Reserved"
        ADOPTED = "adopted", "Adopted"
        UNDER_MEDICAL_CARE = "under_medical_care", "Under Medical Care"
        INACTIVE = "inactive", "Inactive"

    class Species(models.TextChoices):
        DOG = "dog", "Dog"
        CAT = "cat", "Cat"
        OTHER = "other", "Other"

    class Size(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"
        EXTRA_LARGE = "extra_large", "Extra Large"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        UNKNOWN = "unknown", "Unknown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    species = models.CharField(max_length=20, choices=Species.choices)
    breed = models.CharField(max_length=150, blank=True)
    age_years = models.PositiveIntegerField(
        default=0,
        help_text="Age in years",
        validators=[MinValueValidator(0), MaxValueValidator(MAX_PET_AGE_YEARS)],
    )
    age_months = models.PositiveIntegerField(
        default=0,
        help_text="Age in months (0-11)",
        validators=[MinValueValidator(0), MaxValueValidator(MAX_PET_AGE_MONTHS)],
    )
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.UNKNOWN)
    size = models.CharField(max_length=15, choices=Size.choices, default=Size.MEDIUM)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    color = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    arrival_date = models.DateField(
        null=True, blank=True, help_text="Date the pet arrived at the adoption center"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_vaccinated = models.BooleanField(default=False)
    is_neutered = models.BooleanField(default=False)
    adoption_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def formatted_age(self) -> str:
        y = self.age_years
        m = self.age_months
        if y > 0 and m > 0:
            y_str = "1 year" if y == 1 else f"{y} years"
            m_str = "1 month" if m == 1 else f"{m} months"
            return f"{y_str} and {m_str}"
        if y > 0:
            return "1 year" if y == 1 else f"{y} years"
        return "1 month" if m == 1 else f"{m} months"

    class Meta:
        verbose_name = "Pet"
        verbose_name_plural = "Pets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.species})"


class PetImage(models.Model):
    """Images for a pet."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="pets/images/%Y/%m/")
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pet Image"
        verbose_name_plural = "Pet Images"
        ordering = ["-is_primary", "created_at"]

    def __str__(self):
        return f"Image of {self.pet.name}"
