from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import AdoptionRecord, _generate_transaction_id
from .serializers import AdoptionRecordSerializer, AdoptionCreateSerializer
from .services import (
    is_handover_confirmed, complete_application_adoption,
    cancel_scheduled_adoption, return_completed_adoption,
)
from .pdf import build_adoption_records_pdf
from apps.accounts.permissions import IsStaff
from apps.notifications.models import create_notification
from apps.reports.documents import philippine_now


class AdoptionRecordViewSet(viewsets.ModelViewSet):
    queryset = AdoptionRecord.objects.select_related(
        "pet", "adopter", "staff_member", "application", "appointment"
    ).all()
    serializer_class = AdoptionRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_permissions(self):
        # Adopters may *read* only their own adoption records (the queryset is
        # scoped to adopter=user) — the adopter portal's Adoption Record page
        # retrieves the completed record and its permanent transaction ID.
        # Every write action, status transition, and the PDF export remain
        # staff-only.
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsStaff()]

    def get_queryset(self):
        user = self.request.user
        if user.is_adopter:
            qs = self.queryset.filter(adopter=user)
        else:
            qs = self.queryset
        # Optional filter so the staff Adoption Records page can browse by
        # record status without fetching and filtering pages client-side.
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    @action(detail=True, methods=["get"], url_path="record-pdf")
    def record_pdf(self, request, pk=None):
        """Staff-only document for a completed or returned adoption."""
        record = self.get_object()
        if record.status not in (AdoptionRecord.Status.COMPLETED, AdoptionRecord.Status.RETURNED):
            return Response(
                {"error": "Individual PDF is only available for completed or returned adoption records."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .pdf import build_single_adoption_pdf, build_returned_adoption_pdf
        returned = record.status == AdoptionRecord.Status.RETURNED
        builder = build_returned_adoption_pdf if returned else build_single_adoption_pdf
        pdf_bytes = builder(record, downloaded_by=request.user)
        prefix = "adoption-return" if returned else "adoption"
        filename = f"pawconnect-{prefix}-{record.transaction_id or str(record.id)[:8]}.pdf"
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        resp["Cache-Control"] = "private, no-store"
        return resp

    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        """Staff-only A4 PDF export of adoption records matching ``?status=``.

        Mirrors the payment records export: the same queryset/scoping as the
        list endpoint is reused (staff see all records; adopters are blocked by
        ``IsStaff``), the whole matching set is rendered server-side (not just
        the current pagination page), and nothing is ever mutated — in
        particular, transaction IDs are only read here, never generated or
        modified (that happens exclusively in the completion service).
        """
        status_filter = request.query_params.get("status")
        if status_filter and status_filter not in AdoptionRecord.Status.values:
            return Response(
                {"status": ["Invalid adoption record status filter."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = list(self.filter_queryset(self.get_queryset()).order_by("created_at"))
        filters = [f"Status: {status_filter}"] if status_filter else []

        pdf_bytes = build_adoption_records_pdf(records, filters=filters, downloaded_by=request.user)

        filename = f"pawconnect-adoption-records-{philippine_now().date().isoformat()}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response

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
        if new_status == "cancelled":
            return self._cancel_record(instance, request)
        if new_status == "returned":
            return self._return_record(instance, request)
        if new_status:
            if new_status == instance.status:
                # Idempotent retry with same status - do not re-run transitions or regenerate IDs
                return Response(AdoptionRecordSerializer(instance).data, status=status.HTTP_200_OK)
            if not instance.can_transition_to(new_status):
                return Response(
                    {"error": f"Cannot transition from '{instance.status}' to '{new_status}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            old_status = instance.status
            instance.status = new_status
            if new_status == "completed":
                # Require explicit physical handover confirmation — same rule
                # as the confirm-turnover endpoint.  Route through the service
                # to get atomic row-locking, idempotency, and all business rules.
                is_valid, err_msg = is_handover_confirmed(request.data)
                if not is_valid:
                    return Response({"error": err_msg}, status=status.HTTP_400_BAD_REQUEST)

                app = getattr(instance, "application", None)
                if not app:
                    return Response(
                        {"error": "No associated application found for this adoption record."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    complete_application_adoption(
                        app, request.user, notes=request.data.get("notes", ""), handover_confirmed=True
                    )
                except DjangoValidationError as exc:
                    msg = exc.message if hasattr(exc, "message") else str(exc)
                    return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

                instance.refresh_from_db()
                return Response(AdoptionRecordSerializer(instance).data, status=status.HTTP_200_OK)
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

    def _cancel_record(self, record, request):
        try:
            record = cancel_scheduled_adoption(
                record, request.user, request.data.get("reason"), request.data.get("confirmed")
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdoptionRecordSerializer(record, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._cancel_record(self.get_object(), request)

    def _return_record(self, record, request):
        try:
            record = return_completed_adoption(
                record, request.user, request.data.get("return_reason"), request.data.get("confirmed")
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdoptionRecordSerializer(record, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="mark-returned")
    def mark_returned(self, request, pk=None):
        return self._return_record(self.get_object(), request)
