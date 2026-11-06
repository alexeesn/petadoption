from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import serializers
from apps.health.services import build_adopter_health_summary
from .models import MAX_PET_AGE_MONTHS, MAX_PET_AGE_YEARS, Pet, PetImage, PetDeathRecord


class PetDeathRecordSerializer(serializers.ModelSerializer):
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True)
    corrected_by_email = serializers.EmailField(source="corrected_by.email", read_only=True, default=None)

    class Meta:
        model = PetDeathRecord
        fields = ["id", "death_date", "cause", "veterinarian", "internal_notes", "recorded_at", "recorded_by_email", "corrected_at", "corrected_by_email", "correction_reason"]
        read_only_fields = fields


class RecordPetDeathSerializer(serializers.Serializer):
    death_date = serializers.DateField()
    cause = serializers.CharField(max_length=1000, required=False, default="Unknown")
    veterinarian = serializers.CharField(max_length=200, required=False, default="", allow_blank=True)
    internal_notes = serializers.CharField(max_length=5000, required=False, default="", allow_blank=True)
    confirmed = serializers.BooleanField()


class CorrectPetDeathSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
    confirmed = serializers.BooleanField()


class PetImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PetImage
        fields = ["id", "image", "caption", "is_primary", "created_at"]


class PetSerializer(serializers.ModelSerializer):
    images = PetImageSerializer(many=True, read_only=True)
    # Declared explicitly so the year and month ranges are validated on every
    # write path (create, PUT and PATCH) instead of relying on the model
    # validators, which DRF does not run on its own.
    age_years = serializers.IntegerField(
        min_value=0, max_value=MAX_PET_AGE_YEARS, default=0, required=False
    )
    age_months = serializers.IntegerField(
        min_value=0, max_value=MAX_PET_AGE_MONTHS, default=0, required=False
    )
    # Adopter-safe summary of the staff-managed health record (see
    # apps.health.services). The full record stays behind the staff-only
    # /api/health-records/ endpoints; this field only feeds the adopter-facing
    # Pet Details page.
    health_summary = serializers.SerializerMethodField()
    death_records = serializers.SerializerMethodField()

    def get_death_records(self, obj):
        return PetDeathRecordSerializer(obj.death_records.select_related("recorded_by", "corrected_by"), many=True).data

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get("request"), "user", None)
        if not user or not user.is_authenticated or not (user.is_staff_role or user.is_admin_role):
            fields.pop("death_records", None)
        return fields

    def validate_status(self, value):
        if value == Pet.Status.DECEASED and (not self.instance or self.instance.status != Pet.Status.DECEASED):
            raise serializers.ValidationError("Use Record pet death to confirm and record the details.")
        if self.instance and self.instance.status == Pet.Status.DECEASED and value != Pet.Status.DECEASED:
            raise serializers.ValidationError("Only the administrator death-entry correction action can change this status.")
        if self.instance and self.instance.status == Pet.Status.FOR_ASSESSMENT:
            if value not in (Pet.Status.FOR_ASSESSMENT, Pet.Status.AVAILABLE, Pet.Status.UNDER_MEDICAL_CARE, Pet.Status.INACTIVE):
                raise serializers.ValidationError("Assess the pet and choose Available or Under Medical Care before proceeding with an adoption.")
        return value

    def validate_arrival_date(self, value):
        today = timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()
        if value is not None and value > today:
            raise serializers.ValidationError("Arrival date cannot be in the future.")
        return value

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_years", "age_months", "gender", "size",
            "weight_kg", "color", "description", "arrival_date", "status",
            "is_vaccinated", "is_neutered", "images",
            "health_summary", "death_records", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_health_summary(self, obj):
        return build_adopter_health_summary(obj)


class PetListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_years", "age_months", "gender", "size",
            "weight_kg", "color", "status", "is_vaccinated", "is_neutered",
            "arrival_date", "primary_image", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        if img:
            return PetImageSerializer(img, context=self.context).data
        return None
