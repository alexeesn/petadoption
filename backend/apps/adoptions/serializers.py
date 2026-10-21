from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers

from apps.payments.constants import PROTOTYPE_ADOPTION_FEE
from apps.payments.models import Payment
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
    adoption_fee = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    is_fee_paid = serializers.SerializerMethodField()

    class Meta:
        model = AdoptionRecord
        fields = [
            "id", "transaction_id", "application_id", "pet", "pet_name",
            "adopter", "adopter_email", "staff_member", "staff_email",
            "appointment", "appointment_id", "appointment_date",
            "status", "adoption_date", "completed_date", "completed_at",
            "adoption_fee", "total_paid", "is_fee_paid",
            "notes", "return_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "transaction_id", "application_id", "pet_name",
            "adopter", "adopter_email", "staff_email",
            "appointment", "appointment_id", "appointment_date",
            "completed_date", "completed_at",
            "adoption_fee", "total_paid", "is_fee_paid",
            "created_at", "updated_at",
        ]

    def get_adoption_fee(self, obj):
        return str(PROTOTYPE_ADOPTION_FEE)

    def get_total_paid(self, obj):
        if not obj.application_id:
            return "0.00"
        total = (
            obj.application.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        return f"{total:.2f}"

    def get_is_fee_paid(self, obj):
        if not obj.application_id:
            return False
        total = (
            obj.application.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        return total >= PROTOTYPE_ADOPTION_FEE


class AdoptionCreateSerializer(serializers.Serializer):
    application_id = serializers.UUIDField()
    adoption_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
