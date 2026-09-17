from rest_framework import serializers
from apps.documents.serializers import DocumentSerializer
from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    adopter_email = serializers.EmailField(source="adopter.email", read_only=True)
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    reviewed_by_email = serializers.EmailField(source="reviewed_by.email", read_only=True, default=None)
    # Documents are uploaded as part of the application, so they travel with it
    # for both the adopter's confirmation view and the staff review view.
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = [
            "id", "adopter", "adopter_email", "pet", "pet_name", "status",
            "why_adopt", "experience_with_pets", "living_situation",
            "has_other_pets", "other_pets_description", "references",
            "additional_notes", "staff_notes", "reviewed_by", "reviewed_by_email",
            "reviewed_at", "rejection_reason", "documents", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "adopter", "adopter_email", "pet_name", "reviewed_by",
            "reviewed_by_email", "reviewed_at", "documents", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        status_val = attrs.get("status", self.instance.status if self.instance else None)
        if self.instance:
            pet = self.instance.pet
            adopter = self.instance.adopter
        else:
            pet = attrs.get("pet")
            adopter = self.context["request"].user
        if status_val == "approved" and pet:
            if pet.status not in ["available", "pending"]:
                raise serializers.ValidationError({"status": "Pet is not available for adoption."})
        return attrs

    def to_representation(self, instance):
        # Internal staff notes must never be exposed to adopters
        # (AGENTS.md rule 8 — mirrors Review.internal_notes protection).
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_staff = user and user.is_authenticated and (
            user.is_staff_role or user.is_admin_role
        )
        if not is_staff:
            data.pop("staff_notes", None)
        return data


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = [
            "pet", "why_adopt", "experience_with_pets", "living_situation",
            "has_other_pets", "other_pets_description", "references", "additional_notes",
        ]

    def validate(self, attrs):
        adopter = self.context["request"].user
        pet = attrs.get("pet")
        if pet is not None:
            # A pet cannot be assigned to two conflicting active applications
            # from the same adopter. Active statuses are everything except
            # terminal/cancelled states (mirrors the DB constraint).
            active_statuses = [s for s, _ in Application.Status.choices
                               if s not in ("cancelled", "rejected", "adoption_completed")]
            has_conflict = Application.objects.filter(
                adopter=adopter,
                pet=pet,
                status__in=active_statuses,
            ).exists()
            if has_conflict:
                raise serializers.ValidationError(
                    {"pet": "You already have an active application for this pet."}
                )
        return attrs

    def create(self, validated_data):
        validated_data["adopter"] = self.context["request"].user
        return super().create(validated_data)


class ApplicationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Application.Status.choices)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default="")
    staff_notes = serializers.CharField(required=False, allow_blank=True, default="")
