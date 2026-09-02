from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    application_id = serializers.UUIDField(source="application.id", read_only=True)
    adopter_email = serializers.EmailField(source="application.adopter.email", read_only=True)
    processed_by_email = serializers.EmailField(source="processed_by.email", read_only=True, default=None)
    package_name = serializers.CharField(source="package.name", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            "id", "application", "application_id", "adopter_email", "adoption",
            "package", "package_name", "amount", "method", "status",
            "receipt_number", "reference_number", "notes", "processed_by",
            "processed_by_email", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application_id", "adopter_email", "processed_by",
            "processed_by_email", "package_name", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        if "package" in attrs and attrs["package"]:
            pkg = attrs["package"]
            if pkg.price == 0:
                # Don't create payment for free packages
                raise serializers.ValidationError(
                    {"package": "This is a free package. No payment required."}
                )
        return attrs