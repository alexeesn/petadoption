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

    class Meta:
        model = HealthRecord
        fields = [
            "id", "pet", "pet_name", "veterinarian_name", "veterinary_clinic",
            "diagnosis", "treatment", "notes", "record_date", "next_checkup_date",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "pet_name", "created_by", "created_at", "updated_at",
        ]