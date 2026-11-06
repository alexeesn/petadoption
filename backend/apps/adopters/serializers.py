import json
import os
from functools import lru_cache

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import AdopterProfile, IdentityVerification
from .validators import birthday_error
from apps.accounts.names import display_name

# ---------------------------------------------------------------------------
# File validation constants for identity verification uploads
# ---------------------------------------------------------------------------
_MAX_COMBINED_PDF_SIZE = 20 * 1024 * 1024   # 20 MB
_MAX_SELFIE_SIZE = 10 * 1024 * 1024          # 10 MB
_ALLOWED_PDF_EXTENSIONS = {".pdf"}
_ALLOWED_PDF_MIMES = {"application/pdf"}
_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}


def _validate_pdf(value):
    """Validate a combined-PDF upload: extension, MIME type, and size."""
    if value.size > _MAX_COMBINED_PDF_SIZE:
        raise serializers.ValidationError("Combined PDF must be 20 MB or smaller.")
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in _ALLOWED_PDF_EXTENSIONS:
        raise serializers.ValidationError(
            f"Only PDF files are accepted for the combined document (got '{ext}').")
    content_type = getattr(value, "content_type", None)
    if content_type and content_type not in _ALLOWED_PDF_MIMES:
        raise serializers.ValidationError(
            f"File MIME type '{content_type}' does not match a PDF.")
    return value


def _validate_image(value):
    """Validate a selfie-with-ID image upload: extension, MIME type, and size."""
    if value.size > _MAX_SELFIE_SIZE:
        raise serializers.ValidationError("Selfie image must be 10 MB or smaller.")
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise serializers.ValidationError(
            f"Only JPEG, PNG, or WebP images are accepted for the selfie (got '{ext}').")
    content_type = getattr(value, "content_type", None)
    if content_type and content_type not in _ALLOWED_IMAGE_MIMES:
        raise serializers.ValidationError(
            f"File MIME type '{content_type}' does not match a supported image format.")
    return value


@lru_cache(maxsize=1)
def get_philippine_addresses():
    data_path = os.path.join(os.path.dirname(__file__), "data", "philippine_addresses.json")
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


class AdopterProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    # Single source of truth for "profile complete" (AdopterProfile.is_complete).
    # Both portals read this flag to decide whether an adopter may start a new
    # adoption application.
    profile_is_complete = serializers.SerializerMethodField()
    # Quick status indicator for the adopter portal and staff portal to surface
    # whether identity verification has been submitted/approved.
    identity_verification_status = serializers.SerializerMethodField()

    class Meta:
        model = AdopterProfile
        fields = [
            "id", "user_email", "user_name", "first_name", "last_name", "phone_number",
            "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents", "has_yard",
            "other_pets", "household_members", "agree_to_terms",
            "has_children", "number_of_children", "children_ages",
            "has_other_pets",
            "profile_is_complete", "identity_verification_status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user_email", "user_name", "created_at", "updated_at"]

    def get_user_name(self, obj):
        return obj.user.full_name

    def get_profile_is_complete(self, obj):
        return obj.is_complete()

    def get_identity_verification_status(self, obj):
        """Return the adopter's identity verification status or 'not_submitted'."""
        iv = getattr(obj, "identity_verification", None)
        if iv is None:
            return "not_submitted"
        return iv.status


class AdopterProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", max_length=150, allow_blank=False)
    last_name = serializers.CharField(source="user.last_name", max_length=150, allow_blank=False)
    date_of_birth = serializers.DateField(required=True, allow_null=False)

    def validate_first_name(self, value):
        return display_name(value)

    def validate_last_name(self, value):
        return display_name(value)

    class Meta:
        model = AdopterProfile
        fields = [
            "first_name", "last_name", "phone_number", "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents",
            "has_yard", "other_pets", "household_members", "agree_to_terms",
            "has_children", "number_of_children", "children_ages",
            "has_other_pets",
        ]

    def validate_date_of_birth(self, value):
        error = birthday_error(value)
        if error:
            raise serializers.ValidationError(error)
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        names = validated_data.pop("user", {})
        instance = super().update(instance, validated_data)
        if names:
            for field, value in names.items():
                setattr(instance.user, field, value)
            instance.user.save(update_fields=[*names, "updated_at"])
        return instance

    def validate_household_members(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Household members must be at least 1.")
        return value

    def validate_number_of_children(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Number of children cannot be negative.")
        if value is not None and value > 50:
            raise serializers.ValidationError("Number of children must be 50 or fewer.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        errors = {}
        names = attrs.get("user", {})
        for field in ("first_name", "last_name"):
            value = names.get(field, getattr(getattr(self.instance, "user", None), field, ""))
            if not str(value or "").strip():
                errors[field] = "This field is required."
        error = birthday_error(attrs.get("date_of_birth", getattr(self.instance, "date_of_birth", None)))
        if error:
            errors["date_of_birth"] = error
        if errors:
            raise serializers.ValidationError(errors)

        # Retrieve effective address values (newly provided or existing instance)
        region = attrs.get("region") if "region" in attrs else getattr(self.instance, "region", "")
        region = (region or "").strip()

        # Only validate hierarchical consistency if region is specified (Philippine address)
        if region:
            dataset = get_philippine_addresses()
            reg_obj = next((r for r in dataset if r["name"].strip().lower() == region.lower()), None)
            if not reg_obj:
                raise serializers.ValidationError({"region": f"'{region}' is not a recognized Philippine region."})

            provinces = reg_obj.get("provinces", [])
            is_no_prov = len(provinces) == 0

            state = attrs.get("state") if "state" in attrs else getattr(self.instance, "state", "")
            state = (state or "").strip()

            city = attrs.get("city") if "city" in attrs else getattr(self.instance, "city", "")
            city = (city or "").strip()

            barangay = attrs.get("barangay") if "barangay" in attrs else getattr(self.instance, "barangay", "")
            barangay = (barangay or "").strip()

            if is_no_prov:
                # NCR and regions without provinces: province is not applicable
                attrs["state"] = ""
                available_cities = reg_obj.get("cities", [])
            else:
                # Province is required when region has provinces and city/barangay are submitted
                if not state:
                    if city or barangay:
                        raise serializers.ValidationError({"state": f"Province is required for {reg_obj['name']}."})
                    available_cities = []
                else:
                    prov_obj = next((p for p in provinces if p["name"].strip().lower() == state.lower()), None)
                    if not prov_obj:
                        raise serializers.ValidationError(
                            {"state": f"'{state}' is not a valid province in {reg_obj['name']}."}
                        )
                    available_cities = prov_obj.get("cities", [])

            if city:
                clean_city = city.lower().replace(" (capital)", "").strip()
                city_obj = next(
                    (
                        c for c in available_cities
                        if c["name"].strip().lower() == city.lower()
                        or c["name"].lower().replace(" (capital)", "").strip() == clean_city
                    ),
                    None,
                )
                if not city_obj:
                    parent_desc = state if not is_no_prov else reg_obj["name"]
                    raise serializers.ValidationError(
                        {"city": f"'{city}' is not a valid city/municipality in {parent_desc}."}
                    )

                if barangay:
                    available_barangays = city_obj.get("barangays", [])
                    brgy_match = any(b["name"].strip().lower() == barangay.lower() for b in available_barangays)
                    if not brgy_match:
                        raise serializers.ValidationError(
                            {"barangay": f"'{barangay}' is not a valid barangay in {city_obj['name']}."}
                        )

        # ---- Children validation ----
        has_children = attrs.get("has_children") if "has_children" in attrs else getattr(self.instance, "has_children", False)
        if not has_children:
            attrs["number_of_children"] = None
            attrs["children_ages"] = ""
        else:
            num_children = attrs.get("number_of_children") if "number_of_children" in attrs else getattr(self.instance, "number_of_children", None)
            ages_str = (attrs.get("children_ages") if "children_ages" in attrs else getattr(self.instance, "children_ages", "") or "").strip()

            if num_children is not None:
                if num_children < 1:
                    raise serializers.ValidationError({"number_of_children": "Number of children must be at least 1."})
                if not ages_str:
                    raise serializers.ValidationError({"children_ages": f"Expected {num_children} ages, but none were provided."})
                raw_parts = [p.strip() for p in ages_str.split(",")]
                if any(p == "" for p in raw_parts):
                    raise serializers.ValidationError({"children_ages": "Blank age entries are not allowed."})
                if len(raw_parts) != num_children:
                    raise serializers.ValidationError({
                        "children_ages": f"Expected {num_children} ages for {num_children} children, but received {len(raw_parts)}."
                    })
                parts = raw_parts
            elif ages_str:
                raw_parts = [p.strip() for p in ages_str.split(",")]
                if any(p == "" for p in raw_parts):
                    raise serializers.ValidationError({"children_ages": "Blank age entries are not allowed."})
                parts = raw_parts
            else:
                parts = []

            for part in parts:
                try:
                    age = int(part)
                    if age < 0 or age > 17:
                        raise serializers.ValidationError({"children_ages": f"Age '{part}' must be between 0 and 17."})
                except ValueError:
                    raise serializers.ValidationError({"children_ages": f"'{part}' is not a valid age. Enter whole numbers separated by commas."})

            if parts:
                attrs["children_ages"] = ", ".join(parts)

        # ---- Other pets validation ----
        has_other_pets = attrs.get("has_other_pets") if "has_other_pets" in attrs else getattr(self.instance, "has_other_pets", False)
        if not has_other_pets:
            attrs["other_pets"] = ""

        return attrs


# ---------------------------------------------------------------------------
# IdentityVerification serializers
# ---------------------------------------------------------------------------

class IdentityVerificationSerializer(serializers.ModelSerializer):
    """Read-only adopter-facing view of their own verification record.

    Fields excluded from adopter view:
    - reviewed_by  (staff identity)
    - reviewed_at  (staff decision timing, only rejection_reason matters to adopter)
    Rejection reason IS shown so the adopter knows what to fix.
    """
    can_resubmit = serializers.SerializerMethodField()
    has_combined_pdf = serializers.SerializerMethodField()
    has_selfie_with_id = serializers.SerializerMethodField()
    # Download URLs are authenticated server-side; we return them as relative API paths.
    combined_pdf_url = serializers.SerializerMethodField()
    selfie_with_id_url = serializers.SerializerMethodField()

    class Meta:
        model = IdentityVerification
        fields = [
            "id", "status", "rejection_reason",
            "privacy_consent", "consent_given_at",
            "submitted_at", "created_at", "updated_at",
            "can_resubmit", "has_combined_pdf", "has_selfie_with_id",
            "combined_pdf_url", "selfie_with_id_url",
        ]
        read_only_fields = fields

    def get_can_resubmit(self, obj):
        return obj.can_resubmit()

    def get_has_combined_pdf(self, obj):
        return bool(obj.combined_pdf)

    def get_has_selfie_with_id(self, obj):
        return bool(obj.selfie_with_id)

    def get_combined_pdf_url(self, obj):
        if not obj.combined_pdf:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/api/adopters/verification/download/combined_pdf/")
        return f"/api/adopters/verification/download/combined_pdf/"

    def get_selfie_with_id_url(self, obj):
        if not obj.selfie_with_id:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/api/adopters/verification/download/selfie_with_id/")
        return f"/api/adopters/verification/download/selfie_with_id/"


class IdentityVerificationStaffSerializer(serializers.ModelSerializer):
    """Full staff-facing view, includes reviewer identity and all timestamps."""
    adopter_email = serializers.EmailField(source="profile.user.email", read_only=True)
    adopter_name = serializers.CharField(source="profile.user.full_name", read_only=True)
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )
    can_resubmit = serializers.SerializerMethodField()
    has_combined_pdf = serializers.SerializerMethodField()
    has_selfie_with_id = serializers.SerializerMethodField()
    combined_pdf_url = serializers.SerializerMethodField()
    selfie_with_id_url = serializers.SerializerMethodField()

    class Meta:
        model = IdentityVerification
        fields = [
            "id", "adopter_email", "adopter_name",
            "status", "rejection_reason",
            "privacy_consent", "consent_given_at",
            "reviewed_by", "reviewed_by_email", "reviewed_at",
            "submitted_at", "created_at", "updated_at",
            "can_resubmit", "has_combined_pdf", "has_selfie_with_id",
            "combined_pdf_url", "selfie_with_id_url",
        ]
        read_only_fields = fields

    def get_can_resubmit(self, obj):
        return obj.can_resubmit()

    def get_has_combined_pdf(self, obj):
        return bool(obj.combined_pdf)

    def get_has_selfie_with_id(self, obj):
        return bool(obj.selfie_with_id)

    def _staff_download_url(self, obj, field):
        request = self.context.get("request")
        path = f"/api/adopters/verification-requests/{obj.id}/download/{field}/"
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_combined_pdf_url(self, obj):
        if not obj.combined_pdf:
            return None
        return self._staff_download_url(obj, "combined_pdf")

    def get_selfie_with_id_url(self, obj):
        if not obj.selfie_with_id:
            return None
        return self._staff_download_url(obj, "selfie_with_id")


class IdentityVerificationSubmitSerializer(serializers.Serializer):
    """Write serializer for adopter-initiated (re)submission.

    Validates both files, consent, and business rules (can_resubmit).
    """
    combined_pdf = serializers.FileField(required=True)
    selfie_with_id = serializers.FileField(required=True)
    privacy_consent = serializers.BooleanField(required=True)

    def validate_combined_pdf(self, value):
        return _validate_pdf(value)

    def validate_selfie_with_id(self, value):
        return _validate_image(value)

    def validate_privacy_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must acknowledge the privacy notice before submitting."
            )
        return value

    def validate(self, attrs):
        # Fetch the existing verification record for this adopter (if any)
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            profile = getattr(request.user, "adopter_profile", None)
            if profile:
                iv = getattr(profile, "identity_verification", None)
                if iv and not iv.can_resubmit():
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": (
                                f"You cannot submit while your verification is in '{iv.status}' status. "
                                "Resubmission is only allowed when status is 'not_submitted' or 'rejected'."
                            )
                        }
                    )
        return attrs


class IdentityVerificationReviewSerializer(serializers.Serializer):
    """Write serializer for staff review decisions (approve / reject)."""
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        if attrs["decision"] == "reject" and not attrs.get("rejection_reason", "").strip():
            raise serializers.ValidationError(
                {"rejection_reason": "A rejection reason is required when rejecting a verification request."}
            )
        return attrs
