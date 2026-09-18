from rest_framework import viewsets, generics, permissions, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import Application
from .emails import send_application_approval_email
from .serializers import (
    ApplicationSerializer, ApplicationCreateSerializer,
    ApplicationStatusUpdateSerializer,
)
from apps.accounts.permissions import IsAdopter, IsStaff
from apps.documents.models import Document
from apps.documents.serializers import (
    REQUIRED_DOCUMENT_LABELS, REQUIRED_DOCUMENT_TYPES, validate_uploaded_file,
)
from apps.notifications.models import create_notification


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related(
        "adopter", "adopter__adopter_profile", "pet", "reviewed_by"
    ).prefetch_related("documents").all()
    permission_classes = [permissions.IsAuthenticated]
    # Applications are submitted together with their required documents, so the
    # endpoint has to accept multipart in addition to JSON.
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        # Write access to an application (status, staff_notes, etc.) is
        # staff/admin-only.  Without this, an adopter could PATCH their own
        # application's `status` to "approved" directly (see AGENTS.md #14).
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsStaff()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationCreateSerializer
        if self.action == "update_status":
            return ApplicationStatusUpdateSerializer
        return ApplicationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff_role or user.is_admin_role:
            qs = self.queryset
            status_filter = self.request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
            adopter_id = self.request.query_params.get("adopter_id")
            if adopter_id:
                qs = qs.filter(adopter_id=adopter_id)
            return qs
        return self.queryset.filter(adopter=user)

    def _collect_documents(self, request):
        """Pull the documents submitted alongside the application.

        The adopter portal posts the whole application as one multipart
        request: repeated ``documents`` files paired positionally with
        repeated ``document_types`` values.  Everything is validated *before*
        anything is written, so an application is never created without the
        documents that belong to it.
        """
        data = request.data
        files = data.getlist("documents") if hasattr(data, "getlist") else []
        types = data.getlist("document_types") if hasattr(data, "getlist") else []
        errors = {}

        if len(files) != len(types):
            raise drf_serializers.ValidationError({
                "documents": "Each uploaded document must have a document type."
            })

        valid_types = {choice[0] for choice in Document._meta.get_field("document_type").choices}
        pairs = []
        for doc_type, file_obj in zip(types, files):
            if doc_type not in valid_types:
                errors[doc_type or "documents"] = f"'{doc_type}' is not a valid document type."
                continue
            try:
                validate_uploaded_file(file_obj)
            except drf_serializers.ValidationError as exc:
                errors[doc_type] = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
                continue
            pairs.append((doc_type, file_obj))

        uploaded_types = {doc_type for doc_type, _ in pairs}
        for required in REQUIRED_DOCUMENT_TYPES:
            if required not in uploaded_types and required not in errors:
                label = REQUIRED_DOCUMENT_LABELS.get(required, required)
                errors[required] = f"{label} is required before the application can be submitted."

        if errors:
            raise drf_serializers.ValidationError({"documents": errors})
        return pairs

    def create(self, request, *args, **kwargs):
        # Validate with the write serializer, then respond with the read
        # serializer so the client receives id/status/created_at etc.
        # (see docs/QA-REPORT-2026-09-09.md section 3).
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        documents = self._collect_documents(request)
        # The application and its documents are written together: if a
        # document fails to save, the application is rolled back too, so the
        # adopter never ends up with a submitted application missing its
        # paperwork.
        with transaction.atomic():
            self.perform_create(serializer)
            for doc_type, file_obj in documents:
                Document.objects.create(
                    application=serializer.instance,
                    document_type=doc_type,
                    file=file_obj,
                    original_filename=file_obj.name,
                    content_type=getattr(file_obj, "content_type", "") or "",
                    file_size=file_obj.size,
                    uploaded_by=request.user,
                )
        headers = self.get_success_headers(serializer.data)
        serializer.instance.refresh_from_db()
        read_serializer = ApplicationSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(
            read_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        app = serializer.save(adopter=self.request.user)
        # The draft → submitted auto-advance and its AuditLog entry are now
        # handled by Application.save() so that *every* creation path
        # (API, Django admin, shell, management commands) is covered — see
        # docs/QA-REPORT-2026-09-09.md section 2 and the model's save()
        # override in models.py.
        # Notify the adopter that their application was submitted
        create_notification(
            user=self.request.user,
            title="Application Submitted",
            message=f"Your application for {app.pet.name} has been submitted successfully.",
            notification_type="application",
            link=f"/applications/{app.id}",
        )
        # Notify staff about the new application
        from apps.accounts.models import User
        for staff_user in User.objects.filter(role__in=["staff", "admin"], is_active=True):
            create_notification(
                user=staff_user,
                title="New Application Received",
                message=f"A new application for {app.pet.name} has been submitted.",
                notification_type="application",
                link=f"/applications/{app.id}",
            )

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        app = self.get_object()
        if not (request.user.is_staff_role or request.user.is_admin_role):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ApplicationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        if not app.can_transition_to(new_status):
            return Response(
                {"error": f"Cannot transition from '{app.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status == Application.Status.ADOPTION_COMPLETED:
            # Completing an adoption requires the confirmed onsite visit and a
            # recorded onsite payment, and has adoption-specific side effects,
            # so it goes through the same guarded path as the
            # "complete-adoption" action instead of the generic status update.
            return self._complete_adoption(app, request)
        rejection_reason = serializer.validated_data.get("rejection_reason", "").strip()
        if new_status == "rejected" and not rejection_reason:
            # The staff portal already disables Reject until a reason is typed;
            # enforce the same rule at the API so it cannot be bypassed.
            return Response(
                {"error": "A rejection reason is required when rejecting an application."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_status = app.status
        app.status = new_status
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        if "rejection_reason" in serializer.validated_data:
            app.rejection_reason = serializer.validated_data["rejection_reason"]
        if "staff_notes" in serializer.validated_data:
            app.staff_notes = serializer.validated_data["staff_notes"]
        app.save()

        # Audit log
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action="status_change",
            model_name="Application",
            object_id=str(app.id),
            previous_value=old_status,
            new_value=new_status,
        )

        # Notify the adopter of the status change
        status_messages = {
            "approved": f"Your application for {app.pet.name} has been approved!",
            "rejected": f"Your application for {app.pet.name} has been rejected.",
            "pending_documents": f"Your application for {app.pet.name} requires additional documents.",
            "under_review": f"Your application for {app.pet.name} is now under review.",
            "additional_info_requested": f"Additional information is required for your application for {app.pet.name}.",
        }
        title_messages = {
            "approved": "Application Approved",
            "rejected": "Application Rejected",
            "pending_documents": "Documents Required",
            "under_review": "Application Under Review",
            "additional_info_requested": "Additional Information Required",
        }
        create_notification(
            user=app.adopter,
            title=title_messages.get(new_status, "Application Status Updated"),
            message=status_messages.get(new_status, f"Your application status has been updated to '{new_status}'."),
            notification_type="application",
            link=f"/applications/{app.id}",
        )

        # Sync pet status on approval.  (adoption_completed is handled by
        # _complete_adoption above, which owns the adoption side effects.)
        if new_status == "approved":
            app.pet.status = "pending"
            app.pet.save(update_fields=["status"])
            # A real transition into "approved" (the invalid
            # approved -> approved repeat is rejected with 400 above), so
            # notify the adopter by email exactly once.
            send_application_approval_email(app)

        return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)

    def _complete_adoption(self, app, request):
        """Complete the onsite adoption for *app*.

        Shared by the ``complete-adoption`` action and the generic
        ``update-status`` endpoint so ``adoption_completed`` cannot be reached
        without the onsite requirements being satisfied:

        * the application is approved,
        * the onsite visit date has been confirmed by staff, and
        * the onsite payment has been recorded.

        Recording the payment and completing the adoption are deliberately two
        separate staff actions: this method is only reached when staff ask for
        completion.
        """
        if not (request.user.is_staff_role or request.user.is_admin_role):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        if app.status != Application.Status.APPROVED:
            return Response(
                {"error": "Only an approved application can be completed as an adoption."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.appointments.models import Appointment

        if not app.appointments.filter(status=Appointment.Status.CONFIRMED).exists():
            return Response(
                {
                    "error": (
                        "The onsite visit date must be confirmed before the "
                        "adoption can be completed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not app.payments.exists():
            return Response(
                {"error": "Record the onsite payment before completing the adoption."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.adoptions.services import complete_application_adoption

        notes = (request.data.get("notes") or "").strip()
        if notes:
            # Reuse the existing internal staff-notes field for the onsite
            # transaction note.  ApplicationSerializer strips staff_notes from
            # adopter-facing responses, so the note stays staff-only.
            app.staff_notes = notes
            app.save(update_fields=["staff_notes"])

        with transaction.atomic():
            complete_application_adoption(app, request.user, notes=notes)

        return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="complete-adoption")
    def complete_adoption(self, request, pk=None):
        """Staff/admin completes the onsite adoption from the application page."""
        app = self.get_object()
        return self._complete_adoption(app, request)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        app = self.get_object()
        if app.adopter != request.user:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        if not app.can_transition_to("cancelled"):
            return Response(
                {"error": f"Cannot cancel application in '{app.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_status = app.status
        app.status = "cancelled"
        app.save()
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action="status_change", model_name="Application",
            object_id=str(app.id), previous_value=old_status, new_value="cancelled",
        )
        create_notification(
            user=request.user,
            title="Application Cancelled",
            message=f"Your application for {app.pet.name} has been cancelled.",
            notification_type="application",
            link=f"/applications/{app.id}",
        )
        return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)
