from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError as DjangoValidationError
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
    RescheduleInputSerializer,
    RescheduleRequestSerializer,
)
from .services import ensure_open_application, mark_no_show, request_reschedule


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
        "application", "application__adoption_record", "pet", "adopter", "reviewed_by"
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
                from apps.applications.models import Application
                application = Application.objects.select_for_update().get(pk=application.pk)
                try:
                    ensure_open_application(application)
                    if application.reschedule_requests.filter(status="pending").exists():
                        raise DjangoValidationError("Wait for the pending reschedule request to be reviewed.")
                except DjangoValidationError as exc:
                    return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
                appointment = Appointment.objects.create(
                    application=application,
                    adopter=application.adopter,
                    pet=application.pet,
                    requested_date=serializer.validated_data["requested_date"],
                )
        except IntegrityError:
            # Race between the serializer check and the DB constraint.
            # Only report a duplicate when one actually exists. A schema or
            # other integrity failure must not masquerade as an active request.
            if not Appointment.objects.filter(
                application=application, status__in=Appointment.ACTIVE_STATUSES
            ).exists():
                raise
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
    @transaction.atomic
    def approve(self, request, pk=None):
        """Confirm the requested date: pending_confirmation -> confirmed."""
        appointment = self.get_object()
        if not _can_review(request.user):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        from apps.applications.models import Application
        application = Application.objects.select_for_update().get(pk=appointment.application_id)
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
        try:
            ensure_open_application(application)
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
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
        with transaction.atomic():
            appointment.status = Appointment.Status.CONFIRMED
            appointment.reviewed_by = request.user
            appointment.reviewed_at = timezone.now()
            appointment.save()

            # Confirming the requested date is the scheduling decision: the
            # backend creates (or reuses) the matching AdoptionRecord with
            # status "scheduled" so staff never have to add one by hand.
            # Idempotent, so a repeated/retried approval cannot duplicate it.
            from apps.adoptions.services import schedule_adoption_record_for_appointment

            schedule_adoption_record_for_appointment(appointment, request.user)

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
        transaction.on_commit(lambda: send_appointment_approved_email(appointment))
        return Response(
            AppointmentSerializer(appointment, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="reject")
    @transaction.atomic
    def reject(self, request, pk=None):
        """Reject the requested date: pending_confirmation -> rejected."""
        appointment = self.get_object()
        if not _can_review(request.user):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        from apps.applications.models import Application
        application = Application.objects.select_for_update().get(pk=appointment.application_id)
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
        try:
            ensure_open_application(application)
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

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
        transaction.on_commit(lambda: send_appointment_rejected_email(appointment))
        return Response(
            AppointmentSerializer(appointment, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="mark-no-show")
    def mark_no_show(self, request, pk=None):
        appointment = self.get_object()
        if not _can_review(request.user):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            appointment = mark_no_show(
                appointment, request.user, request.data.get("reason"), request.data.get("confirmed")
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AppointmentSerializer(appointment, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="request-reschedule")
    def request_reschedule(self, request, pk=None):
        appointment = self.get_object()
        if not request.user.is_adopter:
            return Response({"error": "Only adopters can request a new date."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RescheduleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reschedule = request_reschedule(appointment, request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RescheduleRequestSerializer(reschedule).data, status=status.HTTP_201_CREATED)
