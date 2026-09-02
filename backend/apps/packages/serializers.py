from rest_framework import serializers
from .models import AdoptionPackage


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdoptionPackage
        fields = ["id", "name", "description", "price", "inclusions", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]