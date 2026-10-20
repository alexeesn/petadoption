import json
import os
from datetime import date
from functools import lru_cache

from rest_framework import serializers

from .models import AdopterProfile


@lru_cache(maxsize=1)
def get_philippine_addresses():
    data_path = os.path.join(os.path.dirname(__file__), "data", "philippine_addresses.json")
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


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
            "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
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
            "phone_number", "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents",
            "has_yard", "other_pets", "household_members", "agree_to_terms",
        ]

    def validate_date_of_birth(self, value):
        """
        Date of birth is optional (null/blank is accepted).
        When provided it must:
        - Not be in the future.
        - Not be more than 120 years in the past (sanity check).
        """
        if value is None:
            return value
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        min_date = today.replace(year=today.year - 120)
        if value < min_date:
            raise serializers.ValidationError(
                "Date of birth must be within the last 120 years."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # Retrieve effective address values (newly provided or existing instance)
        region = attrs.get("region") if "region" in attrs else getattr(self.instance, "region", "")
        region = (region or "").strip()

        # Only validate hierarchical consistency if region is specified (Philippine address)
        if region:
            dataset = get_philippine_addresses()
            reg_obj = next((r for r in dataset if r["name"].strip().lower() == region.lower()), None)
            if not reg_obj:
                raise serializers.ValidationError({"region": f"'{region}' is not a recognized Philippine region."})

            provinces = reg_obj.get("provinces", [])
            is_no_prov = len(provinces) == 0

            state = attrs.get("state") if "state" in attrs else getattr(self.instance, "state", "")
            state = (state or "").strip()

            city = attrs.get("city") if "city" in attrs else getattr(self.instance, "city", "")
            city = (city or "").strip()

            barangay = attrs.get("barangay") if "barangay" in attrs else getattr(self.instance, "barangay", "")
            barangay = (barangay or "").strip()

            if is_no_prov:
                # NCR and regions without provinces: province is not applicable
                attrs["state"] = ""
                available_cities = reg_obj.get("cities", [])
            else:
                # Province is required when region has provinces and city/barangay are submitted
                if not state:
                    if city or barangay:
                        raise serializers.ValidationError({"state": f"Province is required for {reg_obj['name']}."})
                    available_cities = []
                else:
                    prov_obj = next((p for p in provinces if p["name"].strip().lower() == state.lower()), None)
                    if not prov_obj:
                        raise serializers.ValidationError(
                            {"state": f"'{state}' is not a valid province in {reg_obj['name']}."}
                        )
                    available_cities = prov_obj.get("cities", [])

            if city:
                clean_city = city.lower().replace(" (capital)", "").strip()
                city_obj = next(
                    (
                        c for c in available_cities
                        if c["name"].strip().lower() == city.lower()
                        or c["name"].lower().replace(" (capital)", "").strip() == clean_city
                    ),
                    None,
                )
                if not city_obj:
                    parent_desc = state if not is_no_prov else reg_obj["name"]
                    raise serializers.ValidationError(
                        {"city": f"'{city}' is not a valid city/municipality in {parent_desc}."}
                    )

                if barangay:
                    available_barangays = city_obj.get("barangays", [])
                    brgy_match = any(b["name"].strip().lower() == barangay.lower() for b in available_barangays)
                    if not brgy_match:
                        raise serializers.ValidationError(
                            {"barangay": f"'{barangay}' is not a valid barangay in {city_obj['name']}."}
                        )

        return attrs

