import uuid
from django.db import models
from django.conf import settings


class AdopterProfile(models.Model):
    """Extended profile for adopter users.

    Philippine address hierarchy stored across these fields:
      address_line1  -> house number / street / purok (required)
      address_line2  -> optional additional line
      region         -> Philippine region, e.g. "National Capital Region (NCR)"
      state          -> province (blank for NCR and other no-province regions)
      city           -> city or municipality
      barangay       -> barangay within the city/municipality
      zip_code       -> postal code (required)

    The existing city/state/zip_code columns are preserved as-is to avoid
    data loss for profiles saved before the Philippine address feature.
    New structured fields (region, barangay) are added additively.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="adopter_profile")
    phone_number = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    region = models.CharField(
        max_length=200,
        blank=True,
        help_text="Philippine region (e.g. National Capital Region, Region IV-A)",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City or municipality within the selected region/province",
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="Province (blank for NCR and other no-province regions)",
    )
    barangay = models.CharField(
        max_length=200,
        blank=True,
        help_text="Barangay within the selected city or municipality",
    )
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
    # An adopter must have these contact/address fields saved before they
    # can start a new adoption application (ApplicationCreateSerializer
    # enforces this server-side; the adopter portal mirrors it with the
    # "Complete Your Profile First" gate).
    #
    # Philippine address required fields:
    #   - address_line1  : street address
    #   - region         : region (all areas)
    #   - city           : city or municipality
    #   - barangay       : barangay
    #   - zip_code       : postal code
    #
    # state (province) is intentionally NOT in the required list because
    # NCR adopters legitimately have no province.  The cascading selector
    # enforces consistency at the frontend; backend stores what was saved.
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
        return len(self.missing_required_fields()) == 0

    def missing_required_fields(self):
        """Names of the required profile fields that are still empty.

        Maintains complete backward compatibility with legacy profiles:
        - Legacy profiles: phone_number, address_line1, city, state, zip_code,
          housing_type, owns_or_rents.
        - Philippine-wide profiles: phone_number, address_line1, region, city,
          barangay, zip_code, housing_type, owns_or_rents (and state/province
          only when applicable — NCR has no province).
        """
        missing = []
        for field in ["phone_number", "address_line1", "city"]:
            if not str(getattr(self, field, "") or "").strip():
                missing.append(field)

        region_val = str(getattr(self, "region", "") or "").strip()
        state_val = str(getattr(self, "state", "") or "").strip()
        barangay_val = str(getattr(self, "barangay", "") or "").strip()

        if region_val:
            is_ncr = "NCR" in region_val or "National Capital" in region_val
            if not is_ncr and not state_val:
                missing.append("state")
            if not barangay_val:
                missing.append("barangay")
        else:
            if not state_val:
                missing.append("state")

        for field in ["zip_code", "housing_type", "owns_or_rents"]:
            if not str(getattr(self, field, "") or "").strip():
                missing.append(field)

        return missing

    def __str__(self):
        return f"Profile: {self.user.email}"
