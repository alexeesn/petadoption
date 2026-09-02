from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_email = serializers.EmailField(source="reviewer.email", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "application", "reviewer", "reviewer_email", "decision",
            "internal_notes", "adopter_visible_notes", "created_at",
        ]
        read_only_fields = ["id", "reviewer", "reviewer_email", "created_at"]

    def to_representation(self, instance):
        """Never expose internal_notes to adopter users."""
        rep = super().to_representation(instance)
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if not (request.user.is_staff_role or request.user.is_admin_role):
                rep.pop("internal_notes", None)
        return rep


class ReviewCreateSerializer(serializers.Serializer):
    application = serializers.UUIDField()
    decision = serializers.ChoiceField(choices=Review.Decision.choices)
    internal_notes = serializers.CharField(required=False, allow_blank=True, default="")
    adopter_visible_notes = serializers.CharField(required=False, allow_blank=True, default="")