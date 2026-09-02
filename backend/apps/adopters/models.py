import uuid
from django.db import models
from django.conf import settings


class AdopterProfile(models.Model):
    """Extended profile for adopter users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="adopter_profile")
    phone_number = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    housing_type = models.CharField(
        max_length=20,
        choices=[
            ("house", "House"),
            ("apartment", "Apartment"),
            ("condo", "Condo"),
            ("townhouse", "Townhouse"),
            ("other", "Other"),
        ],
        blank=True,
    )
    owns_or_rents = models.CharField(
        max_length=10,
        choices=[("own", "Own"), ("rent", "Rent"), ("other", "Other")],
        blank=True,
    )
    has_yard = models.BooleanField(default=False)
    other_pets = models.TextField(blank=True, help_text="Describe any current pets")
    household_members = models.IntegerField(default=1)
    agree_to_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Adopter Profile"
        verbose_name_plural = "Adopter Profiles"

    def __str__(self):
        return f"Profile: {self.user.email}"
