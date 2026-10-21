from decimal import Decimal
from rest_framework import serializers
from .constants import PROTOTYPE_ADOPTION_FEE
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    application_id = serializers.UUIDField(source="application.id", read_only=True)
    adopter_email = serializers.EmailField(source="application.adopter.email", read_only=True)
    processed_by_email = serializers.EmailField(source="processed_by.email", read_only=True, default=None)
    package_name = serializers.CharField(source="package.name", read_only=True, default=None)
    adoption_fee = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "application", "application_id", "adopter_email", "adoption",
            "package", "package_name", "amount", "adoption_fee", "method", "status",
            "payment_date", "receipt_number", "reference_number", "notes", "processed_by",
            "processed_by_email", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application_id", "adopter_email", "adoption", "processed_by",
            "processed_by_email", "package_name", "receipt_number", "adoption_fee",
            "created_at", "updated_at",
        ]

    def get_adoption_fee(self, obj):
        return str(PROTOTYPE_ADOPTION_FEE)

    def validate_amount(self, value):
        if value is None or value <= Decimal("0.00"):
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        return value

    def validate(self, attrs):
        if "package" in attrs and attrs["package"]:
            pkg = attrs["package"]
            if pkg.price == 0:
                # Don't create payment for free packages
                raise serializers.ValidationError(
                    {"package": "This is a free package. No payment required."}
                )

        # Prevent reassigning an existing payment to a different application.
        # This protects payment-to-application association integrity on both
        # PATCH and PUT requests.
        if self.instance is not None and "application" in attrs:
            if attrs["application"] != self.instance.application:
                raise serializers.ValidationError(
                    {"application": "An existing payment cannot be reassigned to a different application."}
                )

        return attrs
