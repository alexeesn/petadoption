from rest_framework import serializers
from .models import AdoptionRecord


class AdoptionRecordSerializer(serializers.ModelSerializer):
    adopter_email = serializers.EmailField(source="adopter.email", read_only=True)
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    staff_email = serializers.EmailField(source="staff_member.email", read_only=True, default=None)
    application_id = serializers.UUIDField(source="application.id", read_only=True)

    class Meta:
        model = AdoptionRecord
        fields = [
            "id", "application_id", "pet", "pet_name", "adopter", "adopter_email",
            "staff_member", "staff_email", "status", "adoption_date",
            "completed_date", "notes", "return_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application_id", "pet_name", "adopter", "adopter_email",
            "staff_email", "created_at", "updated_at",
        ]


class AdoptionCreateSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    adoption_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")