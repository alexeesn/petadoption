from rest_framework import generics, viewsets, permissions, status
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import AdoptionRecord
from .serializers import AdoptionRecordSerializer, AdoptionCreateSerializer
from apps.accounts.permissions import IsStaff
from apps.notifications.models import create_notification


class AdoptionRecordViewSet(viewsets.ModelViewSet):
    queryset = AdoptionRecord.objects.select_related(
        "pet", "adopter", "staff_member", "application", "appointment"
    ).all()
    serializer_class = AdoptionRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_adopter:
            return self.queryset.filter(adopter=user)
        return self.queryset

    def create(self, request, *args, **kwargs):
        """Create adoption record from approved application.

        Kept for API compatibility (and for records that have to be created
        without a stored onsite visit).  The normal flow no longer needs it:
        approving the adopter's appointment schedules the record automatically
        (see ``apps.appointments.views.AppointmentViewSet.approve``).

        One record per adoption transaction: an application that already has a
        record gets that record back instead of a duplicate (or a 500 from the
        OneToOne constraint).
        """
        serializer = AdoptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.applications.models import Application
        from apps.appointments.models import Appointment
        application = get_object_or_404(
            Application, id=serializer.validated_data["application_id"]
        )
        if application.status != "approved":
            return Response(
                {"error": "Application must be approved to create an adoption record."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Reference the confirmed onsite visit when there is one, so a record
        # created here still points at the appointment that scheduled it.
        appointment = (
            application.appointments.filter(status=Appointment.Status.CONFIRMED)
            .order_by("-requested_date")
            .first()
        )
        adoption, created = AdoptionRecord.objects.get_or_create(
            application=application,
            defaults={
                "pet": application.pet,
                "adopter": application.adopter,
                "staff_member": request.user,
                "appointment": appointment,
                "adoption_date": serializer.validated_data.get("adoption_date")
                or (appointment.requested_date if appointment else timezone.now().date()),
                "notes": serializer.validated_data.get("notes", ""),
            },
        )
        if not created:
            # Already scheduled/completed by the workflow: reuse, never duplicate.
            return Response(
                AdoptionRecordSerializer(adoption).data, status=status.HTTP_200_OK
            )
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action="adoption_created", model_name="AdoptionRecord",
            object_id=str(adoption.id), previous_value="", new_value="scheduled",
        )
        create_notification(
            user=application.adopter,
            title="Adoption Record Created",
            message=f"An adoption record for {adoption.pet.name} has been created. You will be contacted for scheduling.",
            notification_type="adoption",
            link=f"/adoptions/{adoption.id}",
        )
        return Response(AdoptionRecordSerializer(adoption).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_status = request.data.get("status")
        if new_status:
            if not instance.can_transition_to(new_status):
                return Response(
                    {"error": f"Cannot transition from '{instance.status}' to '{new_status}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            old_status = instance.status
            instance.status = new_status
            if new_status == "completed":
                instance.completed_date = timezone.now().date()
                instance.pet.status = "adopted"
                instance.pet.save(update_fields=["status"])
                # Update application
                instance.application.status = "adoption_completed"
                instance.application.save(update_fields=["status"])
            if new_status == "returned":
                instance.return_reason = request.data.get("return_reason", "")
                instance.pet.status = "available"
                instance.pet.save(update_fields=["status"])
            if new_status == "cancelled":
                instance.pet.status = "available"
                instance.pet.save(update_fields=["status"])
            instance.save()
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user, action="adoption_status_change", model_name="AdoptionRecord",
                object_id=str(instance.id), previous_value=old_status, new_value=new_status,
            )
            # Notify the adopter about adoption status change
            adoption_notifications = {
                "completed": (
                    "Adoption Completed",
                    f"Congratulations! Your adoption of {instance.pet.name} is now complete.",
                ),
                "returned": (
                    "Adoption Returned",
                    f"Your adoption of {instance.pet.name} has been returned.",
                ),
                "cancelled": (
                    "Adoption Cancelled",
                    f"Your adoption of {instance.pet.name} has been cancelled.",
                ),
                "scheduled": (
                    "Adoption Scheduled",
                    f"Your adoption of {instance.pet.name} has been scheduled.",
                ),
            }
            notif_title, notif_message = adoption_notifications.get(
                new_status,
                ("Adoption Updated", f"Your adoption record for {instance.pet.name} has been updated."),
            )
            create_notification(
                user=instance.adopter,
                title=notif_title,
                message=notif_message,
                notification_type="adoption",
                link=f"/adoptions/{instance.id}",
            )
        return super().update(request, *args, **kwargs)