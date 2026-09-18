from rest_framework import serializers

from apps.applications.models import Application

from .models import Appointment, validate_visit_date


class AppointmentSerializer(serializers.ModelSerializer):
    """Read serializer shared by the adopter and staff/admin portals."""

    adopter_email = serializers.EmailField(source="adopter.email", read_only=True)
    adopter_name = serializers.CharField(source="adopter.full_name", read_only=True)
    pet_name = serializers.CharField(source="pet.name", read_only=True)
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )

    class Meta:
        model = Appointment
        fields = [
            "id", "application", "adopter", "adopter_email", "adopter_name",
            "pet", "pet_name", "requested_date", "status",
            "reviewed_by", "reviewed_by_email", "reviewed_at",
            "rejection_reason", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "application", "adopter", "adopter_email", "adopter_name",
            "pet", "pet_name", "status", "reviewed_by", "reviewed_by_email",
            "reviewed_at", "rejection_reason", "created_at", "updated_at",
        ]


class AppointmentCreateSerializer(serializers.Serializer):
    """Input for an adopter submitting a requested onsite visit date."""

    application_id = serializers.UUIDField()
    requested_date = serializers.DateField(validators=[validate_visit_date])

    def validate(self, attrs):
        request = self.context["request"]
        # Scope to the adopter's own applications so another adopter's
        # application id cannot be used (no object-existence leak).
        try:
            application = Application.objects.get(
                id=attrs["application_id"], adopter=request.user
            )
        except Application.DoesNotExist:
            raise serializers.ValidationError(
                {"application_id": "Application not found."}
            )

        # Only an application that staff already approved may book a visit.
        if application.status != Application.Status.APPROVED:
            raise serializers.ValidationError({
                "application_id": (
                    "Only approved applications can book an onsite visit date."
                )
            })

        # One active request at a time per application.  Rejected requests stay
        # in history and do not block a new date.
        if Appointment.objects.filter(
            application=application, status__in=Appointment.ACTIVE_STATUSES
        ).exists():
            raise serializers.ValidationError({
                "application_id": (
                    "This application already has an active appointment request."
                )
            })

        attrs["application"] = application
        return attrs


class AppointmentRejectSerializer(serializers.Serializer):
    """Input for staff/admin rejecting a requested date."""

    reason = serializers.CharField()

    def validate_reason(self, value):
        reason = value.strip()
        if not reason:
            raise serializers.ValidationError(
                "A reason is required when rejecting an appointment date."
            )
        return reason