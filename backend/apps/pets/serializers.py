from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import serializers
from apps.health.services import build_adopter_health_summary
from .models import MAX_PET_AGE_MONTHS, MAX_PET_AGE_YEARS, Pet, PetImage


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
            "health_summary", "created_at", "updated_at",
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
