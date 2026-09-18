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

    # ------------------------------------------------------------------
    # Profile completeness (single source of truth).
    #
    # An adopter must have these contact/housing fields saved before they
    # can start a new adoption application (ApplicationCreateSerializer
    # enforces this server-side; the adopter portal mirrors it with the
    # "Complete Your Profile First" gate).
    #
    # These are exactly the applicant details the staff portal shows in its
    # "Applicant Information" review panel.  address_line2, date_of_birth,
    # has_yard, other_pets and household_members stay optional so this rule
    # never blocks an otherwise complete applicant.
    # ------------------------------------------------------------------
    REQUIRED_PROFILE_FIELDS = [
        "phone_number",
        "address_line1",
        "city",
        "state",
        "zip_code",
        "housing_type",
        "owns_or_rents",
    ]

    def is_complete(self):
        """True when every required profile field has a saved value."""
        return all(str(getattr(self, field, "") or "").strip() for field in self.REQUIRED_PROFILE_FIELDS)

    def missing_required_fields(self):
        """Names of the required profile fields that are still empty."""
        return [
            field
            for field in self.REQUIRED_PROFILE_FIELDS
            if not str(getattr(self, field, "") or "").strip()
        ]

    def __str__(self):
        return f"Profile: {self.user.email}"
