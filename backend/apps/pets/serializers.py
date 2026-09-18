from rest_framework import serializers
from .models import MAX_PET_AGE_YEARS, Pet, PetImage


class PetImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PetImage
        fields = ["id", "image", "caption", "is_primary", "created_at"]


class PetSerializer(serializers.ModelSerializer):
    images = PetImageSerializer(many=True, read_only=True)
    # Declared explicitly so the year range is validated on every write path
    # (create, PUT and PATCH) instead of relying on the model validators, which
    # DRF does not run on its own.
    age_years = serializers.IntegerField(min_value=0, max_value=MAX_PET_AGE_YEARS)

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_years", "gender", "size",
            "weight_kg", "color", "description", "arrival_date", "status",
            "is_vaccinated", "is_neutered", "adoption_fee", "images",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PetListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_years", "gender", "size",
            "color", "status", "is_vaccinated", "is_neutered", "adoption_fee",
            "arrival_date", "primary_image", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        if img:
            return PetImageSerializer(img, context=self.context).data
        return None
