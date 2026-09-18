from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.notifications.models import create_notification

from .emails import (
    send_appointment_approved_email,
    send_appointment_rejected_email,
)
from .models import Appointment
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentRejectSerializer,
    AppointmentSerializer,
)


def _can_review(user):
    return bool(user.is_staff_role or user.is_admin_role)


class AppointmentViewSet(viewsets.ModelViewSet):
    """Onsite visit appointment requests.

    - Adopters create a request for their own *approved* application and may
      only ever read their own appointments.
    - Staff/admin read every request and confirm or reject the requested date.

    Status only changes through the review actions, so PATCH/PUT/DELETE are
    not exposed.
    """

    queryset = Appointment.objects.select_related(
        "application", "pet", "adopter", "reviewed_by"
    ).all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return AppointmentCreateSerializer
        return AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        application_id = self.request.query_params.get("application")
        if user.is_staff_role or user.is_admin_role:
            status_filter = self.request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
        else:
            # Adopters can never see another adopter's appointments.
            qs = qs.filter(adopter=user)
        if application_id:
            qs = qs.filter(application_id=application_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AppointmentCreateSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.validated_data["application"]
        try:
            with transaction.atomic():
                appointment = Appointment.objects.create(
                    application=application,
                    adopter=application.adopter,
                    pet=application.pet,
                    requested_date=serializer.validated_data["requested_date"],
                )
        except IntegrityError:
            # Race between the serializer check and the DB constraint.
            return Response(
                {"error": "This application already has an active appointment request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuditLog.objects.create(
            user=request.user,
            action="appointment_requested",
            model_name="Appointment",
            object_id=str(appointment.id),
            previous_value="",
            new_value=f"pending_confirmation:{appointment.requested_date}",
        )

        # Reuses the existing in-app notification mechanism so staff see the
        # request in the staff portal without a second notification system.
        from apps.accounts.models import User
        for staff_user in User.objects.filter(role__in=["staff", "admin"], is_active=True):
            create_notification(
                user=staff_user,
                title="New Appointment Request",
                message=(
                    f"{application.adopter.email} requested an onsite visit for "
                    f"{appointment.pet.name} on {appointment.requested_date}."
                ),
                notification_type="appointment",
                link="/appointments",
            )

        return Response(
            AppointmentSerializer(appointment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Confirm the requested date: pending_confirmation -> confirmed."""
        appointment = self.get_object()
        if not _can_review(request.user):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        if not appointment.can_transition_to(Appointment.Status.CONFIRMED):
            return Response(
                {
                    "error": (
                        f"Cannot confirm an appointment in "
                        f"'{appointment.status}' status."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = appointment.status
        appointment.status = Appointment.Status.CONFIRMED
        appointment.reviewed_by = request.user
        appointment.reviewed_at = timezone.now()
        appointment.save()

        AuditLog.objects.create(
            user=request.user,
            action="appointment_confirmed",
            model_name="Appointment",
            object_id=str(appointment.id),
            previous_value=old_status,
            new_value=Appointment.Status.CONFIRMED,
        )
        create_notification(
            user=appointment.adopter,
            title="Appointment Confirmed",
            message=(
                f"Your onsite visit for {appointment.pet.name} is confirmed for "
                f"{appointment.requested_date}."
            ),
            notification_type="appointment",
            link=f"/applications/{appointment.application_id}",
        )
        # Only reached on a real pending_confirmation -> confirmed transition
        # (an already-confirmed appointment returned 400 above), so a repeated
        # or retried approve request cannot email the adopter twice.
        send_appointment_approved_email(appointment)
        return Response(
            AppointmentSerializer(appointment, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """Reject the requested date: pending_confirmation -> rejected."""
        appointment = self.get_object()
        if not _can_review(request.user):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AppointmentRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        if not appointment.can_transition_to(Appointment.Status.REJECTED):
            return Response(
                {
                    "error": (
                        f"Cannot reject an appointment in "
                        f"'{appointment.status}' status."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = appointment.status
        appointment.status = Appointment.Status.REJECTED
        appointment.rejection_reason = reason
        appointment.reviewed_by = request.user
        appointment.reviewed_at = timezone.now()
        appointment.save()

        AuditLog.objects.create(
            user=request.user,
            action="appointment_rejected",
            model_name="Appointment",
            object_id=str(appointment.id),
            previous_value=old_status,
            new_value=f"rejected:{reason}",
        )
        # The adoption application itself is intentionally untouched: only the
        # requested date was rejected, so the adopter can pick another date.
        create_notification(
            user=appointment.adopter,
            title="Appointment Date Not Confirmed",
            message=(
                f"Your requested visit date for {appointment.pet.name} "
                f"({appointment.requested_date}) was not confirmed. "
                f"Reason: {reason}. You can choose another date."
            ),
            notification_type="appointment",
            link=f"/applications/{appointment.application_id}",
        )
        # Only reached on a real pending_confirmation -> rejected transition with
        # a validated non-blank reason, so repeating or retrying the reject
        # request cannot email the adopter twice.
        send_appointment_rejected_email(appointment)
        return Response(
            AppointmentSerializer(appointment, context=self.get_serializer_context()).data
        )