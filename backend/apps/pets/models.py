import uuid
from django.db import models


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
        BIRD = "bird", "Bird"
        RABBIT = "rabbit", "Rabbit"
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
    age_months = models.PositiveIntegerField(help_text="Age in months")
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.UNKNOWN)
    size = models.CharField(max_length=15, choices=Size.choices, default=Size.MEDIUM)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_vaccinated = models.BooleanField(default=False)
    is_neutered = models.BooleanField(default=False)
    adoption_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
