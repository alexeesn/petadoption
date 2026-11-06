from decimal import Decimal
from rest_framework import serializers
from .constants import PROTOTYPE_ADOPTION_FEE
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    application_id = serializers.UUIDField(source="application.id", read_only=True)
    adopter_email = serializers.EmailField(source="application.adopter.email", read_only=True)
    # The adopted pet's name, for payment-record listings (the payment itself
    # only stores the application FK; the pet is reached through it).
    pet_name = serializers.CharField(
        source="application.pet.name", read_only=True, default=None
    )
    processed_by_email = serializers.EmailField(source="processed_by.email", read_only=True, default=None)
    package_name = serializers.CharField(source="package.name", read_only=True, default=None)
    adoption_fee = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "application", "application_id", "adopter_email", "adoption",
            "package", "package_name", "amount", "adoption_fee", "method", "status",
            "payment_date", "receipt_number", "reference_number", "notes", "processed_by",
            "processed_by_email", "pet_name", "created_at", "updated_at",
            "death_review_required", "death_review_note",
        ]
        read_only_fields = [
            "id", "application_id", "adopter_email", "adoption", "processed_by",
            "processed_by_email", "package_name", "receipt_number", "adoption_fee",
            "pet_name", "created_at", "updated_at",
            "death_review_required", "death_review_note",
        ]

    def get_adoption_fee(self, obj):
        return str(PROTOTYPE_ADOPTION_FEE)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get("request"), "user", None)
        if not user or not user.is_authenticated or not (user.is_staff_role or user.is_admin_role):
            data.pop("death_review_required", None)
            data.pop("death_review_note", None)
        return data

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

        # Payment integrity gate (Phase 5.2): client input must not be able to
        # mark a payment completed without the intended onsite receipt workflow
        # (record_onsite_payment), which requires staff confirmation that the
        # money was actually received.  Completed is therefore not an
        # acceptable client-supplied status on generic create, and an existing
        # payment cannot be moved *into* completed through PATCH/PUT (moving a
        # completed payment to refunded/failed/cancelled stays allowed).
        if attrs.get("status") == Payment.Status.COMPLETED and (
            self.instance is None or self.instance.status != Payment.Status.COMPLETED
        ):
            raise serializers.ValidationError(
                {
                    "status": (
                        "A payment can only be marked completed through the onsite "
                        "payment flow after the money has actually been received."
                    )
                }
            )

        return attrs
