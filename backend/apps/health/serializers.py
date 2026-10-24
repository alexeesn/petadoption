from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import serializers
from .models import HealthRecord, Vaccination


class VaccinationSerializer(serializers.ModelSerializer):
    vaccination_status = serializers.ReadOnlyField()
    is_due = serializers.ReadOnlyField()

    class Meta:
        model = Vaccination
        fields = [
            "id", "pet", "vaccine_name", "date_administered", "next_due_date",
            "veterinarian", "batch_number", "notes", "vaccination_status",
            "is_due", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HealthRecordSerializer(serializers.ModelSerializer):
    # The staff list shows the pet by name; `pet` alone is a UUID.
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    pet_status = serializers.CharField(source="pet.status", read_only=True)

    def validate(self, attrs):
        today = timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()
        errors = {}
        record_date = attrs.get("record_date")
        next_checkup_date = attrs.get("next_checkup_date")
        if record_date is not None and record_date > today:
            errors["record_date"] = "Record date cannot be in the future."
        if next_checkup_date is not None and next_checkup_date < today:
            errors["next_checkup_date"] = "Next checkup date cannot be in the past."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def validate_pet(self, value):
        if self.instance is not None and value.pk != self.instance.pet_id:
            raise serializers.ValidationError(
                "A health record cannot be moved to another pet. Edit that pet's own record instead."
            )
        return value

    class Meta:
        model = HealthRecord
        fields = [
            "id", "pet", "pet_name", "pet_status", "veterinarian_name", "veterinary_clinic",
            "diagnosis", "treatment", "notes", "record_date", "next_checkup_date",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "pet_name", "pet_status", "created_by", "created_at", "updated_at",
        ]
