import json
import os
from functools import lru_cache

from django.db import transaction
from rest_framework import serializers

from .models import AdopterProfile
from .validators import birthday_error
from apps.accounts.names import display_name


@lru_cache(maxsize=1)
def get_philippine_addresses():
    data_path = os.path.join(os.path.dirname(__file__), "data", "philippine_addresses.json")
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


class AdopterProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    # Single source of truth for "profile complete" (AdopterProfile.is_complete).
    # Both portals read this flag to decide whether an adopter may start a new
    # adoption application.
    profile_is_complete = serializers.SerializerMethodField()

    class Meta:
        model = AdopterProfile
        fields = [
            "id", "user_email", "user_name", "first_name", "last_name", "phone_number",
            "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents", "has_yard",
            "other_pets", "household_members", "agree_to_terms",
            "has_children", "number_of_children", "children_ages",
            "has_other_pets",
            "profile_is_complete", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user_email", "user_name", "created_at", "updated_at"]

    def get_user_name(self, obj):
        return obj.user.full_name

    def get_profile_is_complete(self, obj):
        return obj.is_complete()


class AdopterProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", max_length=150, allow_blank=False)
    last_name = serializers.CharField(source="user.last_name", max_length=150, allow_blank=False)
    date_of_birth = serializers.DateField(required=True, allow_null=False)

    def validate_first_name(self, value):
        return display_name(value)

    def validate_last_name(self, value):
        return display_name(value)

    class Meta:
        model = AdopterProfile
        fields = [
            "first_name", "last_name", "phone_number", "address_line1", "address_line2",
            "region", "city", "state", "barangay", "zip_code",
            "date_of_birth", "housing_type", "owns_or_rents",
            "has_yard", "other_pets", "household_members", "agree_to_terms",
            "has_children", "number_of_children", "children_ages",
            "has_other_pets",
        ]

    def validate_date_of_birth(self, value):
        error = birthday_error(value)
        if error:
            raise serializers.ValidationError(error)
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        names = validated_data.pop("user", {})
        instance = super().update(instance, validated_data)
        if names:
            for field, value in names.items():
                setattr(instance.user, field, value)
            instance.user.save(update_fields=[*names, "updated_at"])
        return instance

    def validate_household_members(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Household members must be at least 1.")
        return value

    def validate_number_of_children(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Number of children cannot be negative.")
        if value is not None and value > 50:
            raise serializers.ValidationError("Number of children must be 50 or fewer.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        errors = {}
        names = attrs.get("user", {})
        for field in ("first_name", "last_name"):
            value = names.get(field, getattr(getattr(self.instance, "user", None), field, ""))
            if not str(value or "").strip():
                errors[field] = "This field is required."
        error = birthday_error(attrs.get("date_of_birth", getattr(self.instance, "date_of_birth", None)))
        if error:
            errors["date_of_birth"] = error
        if errors:
            raise serializers.ValidationError(errors)

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

        # ---- Children validation ----
        has_children = attrs.get("has_children") if "has_children" in attrs else getattr(self.instance, "has_children", False)
        if not has_children:
            attrs["number_of_children"] = None
            attrs["children_ages"] = ""
        else:
            num_children = attrs.get("number_of_children") if "number_of_children" in attrs else getattr(self.instance, "number_of_children", None)
            ages_str = (attrs.get("children_ages") if "children_ages" in attrs else getattr(self.instance, "children_ages", "") or "").strip()

            if num_children is not None:
                if num_children < 1:
                    raise serializers.ValidationError({"number_of_children": "Number of children must be at least 1."})
                if not ages_str:
                    raise serializers.ValidationError({"children_ages": f"Expected {num_children} ages, but none were provided."})
                raw_parts = [p.strip() for p in ages_str.split(",")]
                if any(p == "" for p in raw_parts):
                    raise serializers.ValidationError({"children_ages": "Blank age entries are not allowed."})
                if len(raw_parts) != num_children:
                    raise serializers.ValidationError({
                        "children_ages": f"Expected {num_children} ages for {num_children} children, but received {len(raw_parts)}."
                    })
                parts = raw_parts
            elif ages_str:
                raw_parts = [p.strip() for p in ages_str.split(",")]
                if any(p == "" for p in raw_parts):
                    raise serializers.ValidationError({"children_ages": "Blank age entries are not allowed."})
                parts = raw_parts
            else:
                parts = []

            for part in parts:
                try:
                    age = int(part)
                    if age < 0 or age > 17:
                        raise serializers.ValidationError({"children_ages": f"Age '{part}' must be between 0 and 17."})
                except ValueError:
                    raise serializers.ValidationError({"children_ages": f"'{part}' is not a valid age. Enter whole numbers separated by commas."})

            if parts:
                attrs["children_ages"] = ", ".join(parts)

        # ---- Other pets validation ----
        has_other_pets = attrs.get("has_other_pets") if "has_other_pets" in attrs else getattr(self.instance, "has_other_pets", False)
        if not has_other_pets:
            attrs["other_pets"] = ""

        return attrs
