from rest_framework import serializers
from .models import AdoptionRecord


class AdoptionRecordSerializer(serializers.ModelSerializer):
    adopter_email = serializers.EmailField(source="adopter.email", read_only=True)
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    staff_email = serializers.EmailField(source="staff_member.email", read_only=True, default=None)
    application_id = serializers.UUIDField(source="application.id", read_only=True)
    # The confirmed onsite visit this record was scheduled from (if any).
    appointment_id = serializers.UUIDField(source="appointment.id", read_only=True, default=None)
    appointment_date = serializers.DateField(
        source="appointment.requested_date", read_only=True, default=None
    )

    class Meta:
        model = AdoptionRecord
        fields = [
            "id", "application_id", "pet", "pet_name", "adopter", "adopter_email",
            "staff_member", "staff_email", "appointment", "appointment_id",
            "appointment_date", "status", "adoption_date",
            "completed_date", "notes", "return_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application_id", "pet_name", "adopter", "adopter_email",
            "staff_email", "appointment", "appointment_id", "appointment_date",
            "created_at", "updated_at",
        ]


class AdoptionCreateSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    adoption_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")