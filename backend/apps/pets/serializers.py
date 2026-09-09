from rest_framework import serializers
from .models import Pet, PetImage


class PetImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PetImage
        fields = ["id", "image", "caption", "is_primary", "created_at"]


class PetSerializer(serializers.ModelSerializer):
    images = PetImageSerializer(many=True, read_only=True)

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_months", "gender", "size",
            "weight_kg", "color", "description", "status", "is_vaccinated",
            "is_neutered", "adoption_fee", "images", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PetListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Pet
        fields = [
            "id", "name", "species", "breed", "age_months", "gender", "size",
            "color", "status", "is_vaccinated", "is_neutered", "adoption_fee",
            "primary_image", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        if img:
            return PetImageSerializer(img, context=self.context).data
        return None
