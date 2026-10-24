from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers

from apps.adopters.serializers import AdopterProfileSerializer
from apps.adopters.models import AdopterProfile
from apps.documents.serializers import DocumentSerializer
from apps.payments.constants import PROTOTYPE_ADOPTION_FEE
from apps.payments.models import Payment
from apps.appointments.eligibility import onsite_visit_state
from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    def validate_status(self, value):
        if self.instance is not None and self.instance.status == "cancelled" and value != "cancelled":
            raise serializers.ValidationError("A cancelled application cannot be reopened.")
        if self.instance is not None and self.instance.status == "approved" and value == "cancelled":
            raise serializers.ValidationError("Cancel the scheduled adoption through the adoption cancellation action.")
        if self.instance is not None and self.instance.status == "approved" and value != "approved":
            raise serializers.ValidationError("Use the coordinated adoption action to complete or cancel an approved application.")
        return value

    adopter_email = serializers.EmailField(source="adopter.email", read_only=True)
    # Applicant information for the staff review page.  A user always has an
    # email, but the one-to-one profile is created lazily, so it is resolved
    # defensively (see get_adopter_profile).
    adopter_name = serializers.CharField(source="adopter.full_name", read_only=True)
    adopter_profile = serializers.SerializerMethodField()
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)
    # Documents are uploaded as part of the application, so they travel with it
    # for both the adopter's confirmation view and the staff review view.
    documents = DocumentSerializer(many=True, read_only=True)
    adoption_fee = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    is_fee_paid = serializers.SerializerMethodField()
    turnover_eligible = serializers.SerializerMethodField()
    onsite_visit = serializers.SerializerMethodField()

    def get_onsite_visit(self, obj):
        return onsite_visit_state(obj)

    class Meta:
        model = Application
        fields = [
            "id", "adopter", "adopter_email", "adopter_name", "adopter_profile",
            "pet", "pet_name", "status",
            "why_adopt", "experience_with_pets", "living_situation",
            "has_other_pets", "other_pets_description", "references",
            "additional_notes", "privacy_consent", "require_home_visit", "no_home_visit_reason",
            "staff_notes", "reviewed_by", "reviewed_by_email",
            "reviewed_at", "rejection_reason", "documents",
            "adoption_fee", "total_paid", "is_fee_paid", "turnover_eligible", "onsite_visit",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "adopter", "adopter_email", "adopter_name", "adopter_profile",
            "pet_name", "reviewed_by",
            "reviewed_by_email", "reviewed_at", "documents",
            "adoption_fee", "total_paid", "is_fee_paid", "turnover_eligible", "onsite_visit",
            "created_at", "updated_at",
            "has_other_pets", "other_pets_description",
        ]

    def get_adopter_profile(self, obj):
        # Staff need the adopter's contact/household details to review an
        # application.  Reverse one-to-one access raises
        # RelatedObjectDoesNotExist when the profile was never created, so use
        # getattr with a default instead of touching obj.adopter.adopter_profile.
        profile = getattr(obj.adopter, "adopter_profile", None)
        if profile is None:
            return None
        return AdopterProfileSerializer(profile, context=self.context).data

    def get_adoption_fee(self, obj):
        return str(PROTOTYPE_ADOPTION_FEE)

    def get_total_paid(self, obj):
        total = (
            obj.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        return f"{total:.2f}"

    def get_is_fee_paid(self, obj):
        total = (
            obj.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        return total >= PROTOTYPE_ADOPTION_FEE

    def get_turnover_eligible(self, obj):
        if obj.status != Application.Status.APPROVED:
            return False
        if not onsite_visit_state(obj)["date_reached"]:
            return False
        total = (
            obj.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        return total >= PROTOTYPE_ADOPTION_FEE

    def validate(self, attrs):
        status_val = attrs.get("status", self.instance.status if self.instance else None)
        if self.instance:
            pet = self.instance.pet
            adopter = self.instance.adopter
        else:
            pet = attrs.get("pet")
            adopter = self.context["request"].user
        if status_val == "approved" and pet:
            if pet.status not in ["available", "pending"]:
                raise serializers.ValidationError({"status": "Pet is not available for adoption."})
        return attrs

    def to_representation(self, instance):
        # Internal staff notes must never be exposed to adopters
        # (AGENTS.md rule 8 — mirrors Review.internal_notes protection).
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_staff = user and user.is_authenticated and (
            user.is_staff_role or user.is_admin_role
        )
        if not is_staff:
            data.pop("staff_notes", None)
        return data


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            "pet", "why_adopt", "experience_with_pets", "living_situation",
            "references", "additional_notes",
            "privacy_consent", "require_home_visit", "no_home_visit_reason",
        ]

    def validate(self, attrs):
        adopter = self.context["request"].user

        # ------------------------------------------------------------------
        # Consent validation
        # ------------------------------------------------------------------
        if not attrs.get("privacy_consent", False):
            raise serializers.ValidationError({"privacy_consent": "Privacy consent is required."})

        # ------------------------------------------------------------------
        # Home visit validation
        # ------------------------------------------------------------------
        if not attrs.get("require_home_visit", True):
            if not attrs.get("no_home_visit_reason"):
                raise serializers.ValidationError({"no_home_visit_reason": "Reason is required if home visit is declined."})

        # ------------------------------------------------------------------
        # An adopter must have a complete saved profile before starting a new
        # application.  Enforced here — the single creation path — so the rule
        # holds no matter how the request reaches the API (AGENTS.md #4:
        # never rely only on React route protection or button hiding).
        # Staff/admin are exempt: they are not applicants being vetted.
        # Create-only: this check never touches existing applications.
        # ------------------------------------------------------------------
        if adopter.is_adopter:
            profile = getattr(adopter, "adopter_profile", None)
            if profile is None or not profile.is_complete():
                missing = (
                    profile.missing_required_fields() if profile
                    else list(AdopterProfile.REQUIRED_PROFILE_FIELDS)
                )
                raise serializers.ValidationError(
                    {
                        "profile": (
                            "Your profile information is incomplete. Please update and save "
                            "your profile before starting an adoption application. "
                            f"Missing: {', '.join(missing)}."
                        )
                    }
                )

        pet = attrs.get("pet")
        if pet is not None:
            if pet.status in ("for_assessment", "under_medical_care"):
                raise serializers.ValidationError({"pet": "This pet is awaiting assessment or medical clearance and is not available for adoption."})
            # A pet cannot be assigned to two conflicting active applications
            # from the same adopter. Active statuses are everything except
            # terminal/cancelled states (mirrors the DB constraint).
            active_statuses = [s for s, _ in Application.Status.choices
                               if s not in ("cancelled", "rejected", "adoption_completed")]
            has_conflict = Application.objects.filter(
                adopter=adopter,
                pet=pet,
                status__in=active_statuses,
            ).exists()
            if has_conflict:
                raise serializers.ValidationError(
                    {"pet": "You already have an active application for this pet."}
                )
        return attrs

    def create(self, validated_data):
        validated_data["adopter"] = self.context["request"].user
        # Household pet information is entered once in the adopter profile.
        # Retain a submission-time snapshot without trusting duplicate form input.
        profile = AdopterProfile.objects.filter(user=validated_data["adopter"]).first()
        validated_data["has_other_pets"] = bool(profile and profile.has_other_pets)
        validated_data["other_pets_description"] = profile.other_pets if profile and profile.has_other_pets else ""
        return super().create(validated_data)


class ApplicationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Application.Status.choices)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default="")
    staff_notes = serializers.CharField(required=False, allow_blank=True, default="")
