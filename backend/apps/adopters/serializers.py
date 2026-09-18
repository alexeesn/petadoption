from rest_framework import serializers
from .models import AdopterProfile


class AdopterProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    # Single source of truth for "profile complete" (AdopterProfile.is_complete).
    # Both portals read this flag to decide whether an adopter may start a new
    # adoption application.
    profile_is_complete = serializers.SerializerMethodField()

    class Meta:
        model = AdopterProfile
        fields = [
            "id", "user_email", "user_name", "phone_number",
            "address_line1", "address_line2", "city", "state", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents", "has_yard",
            "other_pets", "household_members", "agree_to_terms",
            "profile_is_complete", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user_email", "user_name", "created_at", "updated_at"]

    def get_user_name(self, obj):
        return obj.user.full_name

    def get_profile_is_complete(self, obj):
        return obj.is_complete()


class AdopterProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdopterProfile
        fields = [
            "phone_number", "address_line1", "address_line2", "city", "state",
            "zip_code", "date_of_birth", "housing_type", "owns_or_rents",
            "has_yard", "other_pets", "household_members", "agree_to_terms",
        ]
