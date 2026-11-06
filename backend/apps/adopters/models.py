import uuid
from django.db import models
from django.conf import settings


def identity_verification_upload_path(instance, filename):
    """Generate a secure, non-guessable path for identity verification files."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    safe_name = uuid.uuid4().hex
    return f"identity_docs/{safe_name}.{ext}"


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
    has_children = models.BooleanField(
        default=False,
        help_text="Whether the household has children",
    )
    number_of_children = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of children in the household (only when has_children=True)",
    )
    children_ages = models.CharField(
        max_length=200,
        blank=True,
        help_text="Comma-separated ages of children, e.g. '3, 7, 12'",
    )
    has_other_pets = models.BooleanField(
        default=False,
        help_text="Whether the household currently has other pets",
    )
    agree_to_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Adopter Profile"
        verbose_name_plural = "Adopter Profiles"

    # ------------------------------------------------------------------
    # Profile completeness (single source of truth).
    #
    # An adopter must have their first/last name, an adult birthday, and these
    # contact/address fields saved before they
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
        "first_name",
        "last_name",
        "date_of_birth",
    ]

    def is_complete(self):
        """True when identity, adult birthday and required contact details are valid."""
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

        for field in ("first_name", "last_name"):
            if not str(getattr(self.user, field, "") or "").strip():
                missing.append(field)
        from .validators import birthday_error
        if birthday_error(self.date_of_birth):
            missing.append("date_of_birth")
        return missing

    def __str__(self):
        return f"Profile: {self.user.email}"


class IdentityVerification(models.Model):
    """
    Reusable, profile-level identity and document verification for an adopter.

    An adopter uploads a combined PDF (containing their valid ID, proof of
    address, and barangay certification) and a selfie-with-ID image once.
    Authorised staff review and approve or reject the submission.
    A verified record is then associated with future adoption applications so
    that the same general documents do not need to be re-uploaded per pet.

    Status lifecycle:
      not_submitted  ──► pending_review  ──► verified
                              │
                              └──► rejected  ──► pending_review (after resubmit)

    Business rules:
    - Adopters CANNOT change status to verified themselves.
    - Resubmission is only possible from not_submitted or rejected states.
    - Replacing files while verified triggers a re-review (back to pending_review).
    - Application submission requires status == verified.
    - Staff rejection requires a written reason.

    Privacy:
    - Files are stored with generated names (identity_verification_upload_path).
    - Files are never served via public static URLs; always through an
      authenticated Django download view.
    - Internal staff notes (reviewed_by, reviewed_at, rejection_reason) are
      exposed only to staff; the adopter sees rejection_reason only when
      status == rejected.

    Retention: documents should be reviewed per org policy. The shelter should
    confirm how long to retain ID copies after adoption completion or account
    closure. See docs/AGENT-SPEC.md §20.
    """

    class Status(models.TextChoices):
        NOT_SUBMITTED = "not_submitted", "Not Submitted"
        PENDING_REVIEW = "pending_review", "Pending Review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    # States from which a resubmission is accepted
    RESUBMITTABLE_STATUSES = {Status.NOT_SUBMITTED, Status.REJECTED}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(
        AdopterProfile,
        on_delete=models.CASCADE,
        related_name="identity_verification",
    )
    # Combined PDF containing: valid ID, proof of address, barangay certification.
    # Null/blank until the adopter first submits.
    combined_pdf = models.FileField(
        upload_to=identity_verification_upload_path,
        null=True,
        blank=True,
        help_text="Single PDF combining: valid ID, proof of address, barangay certification",
    )
    # Clear photo of adopter's face while holding their valid ID.
    selfie_with_id = models.FileField(
        upload_to=identity_verification_upload_path,
        null=True,
        blank=True,
        help_text="Photo: adopter face visible and holding valid ID",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_SUBMITTED,
        db_index=True,
    )
    # Staff-written reason returned to adopter when rejected
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason given to adopter when status is rejected (required when rejecting)",
    )
    # Explicit informed-consent before submission
    privacy_consent = models.BooleanField(
        default=False,
        help_text="Adopter acknowledged the privacy notice before submitting",
    )
    consent_given_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when privacy consent was recorded",
    )
    # Review metadata
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_reviews",
        help_text="Staff/admin who made the last review decision",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Most recent submission timestamp",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Identity Verification"
        verbose_name_plural = "Identity Verifications"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"IdentityVerification [{self.status}] for {self.profile.user.email}"

    def can_resubmit(self):
        """Return True when the adopter is allowed to (re)submit."""
        return self.status in self.RESUBMITTABLE_STATUSES

    def can_replace_files(self):
        """
        Return True when replacing existing files is permitted.
        Replacing verified files requires a new review; rejected allows free replacement.
        """
        return self.status != IdentityVerification.Status.PENDING_REVIEW
