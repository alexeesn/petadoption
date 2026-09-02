from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    generated_by_email = serializers.EmailField(source="generated_by.email", read_only=True, default=None)

    class Meta:
        model = Report
        fields = ["id", "name", "report_type", "parameters", "generated_by", "generated_by_email", "created_at"]
        read_only_fields = ["id", "generated_by", "generated_by_email", "created_at"]
