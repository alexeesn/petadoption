from pathlib import Path

from rest_framework import serializers

from apps.pets.models import MAX_PET_AGE_MONTHS, MAX_PET_AGE_YEARS, Pet
from .models import SurrenderEvent, SurrenderPhoto, SurrenderRequest


class SurrenderWriteSerializer(serializers.ModelSerializer):
    ownership_confirmed = serializers.BooleanField(required=True)
    age_years = serializers.IntegerField(min_value=0, max_value=MAX_PET_AGE_YEARS)
    age_months = serializers.IntegerField(min_value=0, max_value=MAX_PET_AGE_MONTHS)

    def validate_ownership_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("Confirm that you own this pet or are authorized to surrender it.")
        return value

    def validate_contact_number(self, value):
        digits = ''.join(c for c in value if c.isdigit())
        if not 7 <= len(digits) <= 15 or any(c not in '+()- .0123456789' for c in value):
            raise serializers.ValidationError("Enter a valid contact number (7 to 15 digits).")
        return value

    class Meta:
        model = SurrenderRequest
        fields = ["pet_name", "species", "breed", "age_years", "age_months", "gender", "reason", "health_information", "behavior_information", "contact_number", "ownership_confirmed"]
        extra_kwargs = {field: {"max_length": 5000} for field in ("reason", "health_information", "behavior_information")}


class PhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

    def to_internal_value(self, data):
        # Django's ImageField replaces content_type with Pillow's detected
        # type. Preserve/check the client declaration before that happens.
        file = data.get("image")
        expected = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        if file and file.size > 5 * 1024 * 1024:
            raise serializers.ValidationError({"image": "Each photo must be 5 MB or smaller."})
        if file and getattr(file, "content_type", "") != expected.get(Path(file.name).suffix.lower()):
            raise serializers.ValidationError({"image": "The photo MIME type must match its extension."})
        return super().to_internal_value(data)

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Each photo must be 5 MB or smaller.")
        expected = {".jpg": ("JPEG", "image/jpeg"), ".jpeg": ("JPEG", "image/jpeg"), ".png": ("PNG", "image/png")}
        rule = expected.get(Path(value.name).suffix.lower())
        if not rule or value.image.format != rule[0] or value.content_type != rule[1]:
            raise serializers.ValidationError("Upload a JPEG or PNG whose extension and MIME type match its contents.")
        return value


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurrenderEvent
        fields = ["id", "action", "previous_status", "new_status", "note", "intake_date", "created_at"]


class StaffEventSerializer(EventSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + ["internal_notes", "actor_email"]


class PhotoSerializer(serializers.ModelSerializer):
    # Only IDs, never storage paths or public media URLs.
    class Meta:
        model = SurrenderPhoto
        fields = ["id"]


class SurrenderReadSerializer(serializers.ModelSerializer):
    photos = PhotoSerializer(many=True, read_only=True)
    history = EventSerializer(many=True, read_only=True)

    class Meta:
        model = SurrenderRequest
        fields = ["id", *SurrenderWriteSerializer.Meta.fields, "status", "intake_date", "intake_instructions", "pet", "received_at", "created_at", "updated_at", "photos", "history"]
        read_only_fields = fields


class StaffSurrenderSerializer(SurrenderReadSerializer):
    history = StaffEventSerializer(many=True, read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)

    class Meta(SurrenderReadSerializer.Meta):
        fields = SurrenderReadSerializer.Meta.fields + ["owner_email", "owner_name"]
        read_only_fields = fields


class ReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["needs_information", "waitlisted", "intake_scheduled", "declined"])
    note = serializers.CharField(max_length=2000)
    internal_notes = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    intake_date = serializers.DateField(required=False)
    intake_instructions = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class IntakeSerializer(serializers.Serializer):
    confirmed = serializers.BooleanField()
    pet_status = serializers.ChoiceField(choices=[Pet.Status.FOR_ASSESSMENT, Pet.Status.AVAILABLE, Pet.Status.UNDER_MEDICAL_CARE, Pet.Status.INACTIVE], default=Pet.Status.FOR_ASSESSMENT)
