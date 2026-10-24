from rest_framework import viewsets, generics, permissions, status, filters, serializers as drf_serializers
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
from apps.filters import RecordScopeFilter
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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, RecordScopeFilter]
    active_statuses = Application.ACTIVE_STATUSES
    # Applications are submitted together with their required documents, so the
    # endpoint has to accept multipart in addition to JSON.
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        # Write access to an application (status, staff_notes, etc.) is
        # staff/admin-only.  Without this, an adopter could PATCH their own
        # application's `status` to "approved" directly (see AGENTS.md #14).
        if self.action in (
            "update", "partial_update", "destroy",
            "confirm_turnover", "complete_adoption", "record_payment",
        ):
            return [permissions.IsAuthenticated(), IsStaff()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationCreateSerializer
        if self.action == "update_status":
            return ApplicationStatusUpdateSerializer
        return ApplicationSerializer

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        # A staff edit must not overwrite a cancellation/completion that just
        # committed while this request was waiting for the application row.
        application = self.get_object()
        Application.objects.select_for_update().get(pk=application.pk)
        return super().update(request, *args, **kwargs)

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
        serializer.instance.refresh_from_db()
        read_serializer = ApplicationSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        app = serializer.save(adopter=self.request.user)
        # Fix Finding §2: Ensure application is submitted
        app.status = Application.Status.SUBMITTED
        app.save()
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
        if new_status == "approved" and app.pet.status in ("for_assessment", "under_medical_care"):
            return Response({"error": "The pet needs assessment or medical clearance before approval."}, status=status.HTTP_400_BAD_REQUEST)
        if app.status == Application.Status.APPROVED and new_status == Application.Status.CANCELLED:
            return Response(
                {"error": "Cancel the scheduled adoption from Adoption Records, with a reason and confirmation."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not app.can_transition_to(new_status):
            return Response(
                {"error": f"Cannot transition from '{app.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status == Application.Status.ADOPTION_COMPLETED:
            # Completing an adoption requires the confirmed onsite visit and a
            # recorded onsite payment, and has adoption-specific side effects,
            # so it goes through the same guarded path as the
            # "confirm-turnover" action instead of the generic status update.
            return self._confirm_turnover(app, request)
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
        # _confirm_turnover, which owns the adoption side effects.)
        if new_status == "approved":
            app.pet.status = "pending"
            app.pet.save(update_fields=["status"])
            # A real transition into "approved" (the invalid
            # approved -> approved repeat is rejected with 400 above), so
            # notify the adopter by email exactly once.
            send_application_approval_email(app)

        return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)

    @transaction.atomic
    def _confirm_turnover(self, app, request):
        """Confirm pet turnover and finalize the adoption transaction for *app*.

        Shared by the ``confirm-turnover`` action, legacy ``complete-adoption``
        action, and the generic ``update-status`` endpoint.

        Enforces all of the following:
        1. Only staff or administrator can confirm turnover.
        2. Application must be approved (idempotent if already completed).
        3. Appointment must be confirmed.
        4. The required adoption fee (₱500.00) must be fully paid via completed payment records.
           Pending, failed, or partial payments do not count.
        5. Physical turnover must be explicitly confirmed by staff.
        6. Updates Application, AdoptionRecord, and Pet atomically.
        """
        if not (request.user.is_staff_role or request.user.is_admin_role):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        app = Application.objects.select_for_update().get(pk=app.pk)
        # Idempotent retry: already completed, return serialized data
        if app.status == Application.Status.ADOPTION_COMPLETED:
            if hasattr(app, "adoption_record"):
                return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)

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

        from apps.payments.constants import PROTOTYPE_ADOPTION_FEE
        from apps.payments.models import Payment
        from django.db.models import Sum
        from decimal import Decimal

        if not app.payments.exists():
            return Response(
                {"error": "Record the onsite payment before completing the adoption."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        completed_payments = app.payments.filter(status=Payment.Status.COMPLETED)
        total_completed = (
            completed_payments.aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        if total_completed == Decimal("0.00"):
            return Response(
                {
                    "error": (
                        "Only completed payments count toward the adoption fee. "
                        "Pending or failed payments cannot satisfy the adoption fee."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if total_completed < PROTOTYPE_ADOPTION_FEE:
            return Response(
                {
                    "error": (
                        f"The required adoption fee of ₱{PROTOTYPE_ADOPTION_FEE:.2f} has not been fully paid. "
                        f"Total completed payment is ₱{total_completed:.2f}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Explicit staff confirmation that pet has been physically handed over.
        # Only an actual JSON boolean true is accepted.  Missing fields, false,
        # null, strings, and integers are all rejected.
        from apps.adoptions.services import is_handover_confirmed, complete_application_adoption
        is_valid, err_msg = is_handover_confirmed(request.data)
        if not is_valid:
            return Response({"error": err_msg}, status=status.HTTP_400_BAD_REQUEST)

        notes = (request.data.get("notes") or "").strip()
        if notes:
            # Reuse the existing internal staff-notes field for the onsite
            # transaction note.  ApplicationSerializer strips staff_notes from
            # adopter-facing responses, so the note stays staff-only.
            app.staff_notes = notes
            app.save(update_fields=["staff_notes"])

        from django.core.exceptions import ValidationError
        try:
            complete_application_adoption(app, request.user, notes=notes, handover_confirmed=True)
        except ValidationError as exc:
            transaction.set_rollback(True)
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        app.refresh_from_db()
        return Response(ApplicationSerializer(app, context=self.get_serializer_context()).data)

    def _complete_adoption(self, app, request):
        return self._confirm_turnover(app, request)

    @action(detail=True, methods=["post"], url_path="confirm-turnover")
    def confirm_turnover(self, request, pk=None):
        """Staff/admin confirms physical pet turnover and finalizes adoption."""
        app = self.get_object()
        return self._confirm_turnover(app, request)

    @action(detail=True, methods=["post"], url_path="complete-adoption")
    def complete_adoption(self, request, pk=None):
        """Staff/admin completes the onsite adoption (backward compatible endpoint)."""
        app = self.get_object()
        return self._confirm_turnover(app, request)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        """Staff action to record an on-site payment for this application."""
        if not (request.user.is_staff_role or request.user.is_admin_role):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        app = self.get_object()
        payment_received = request.data.get("payment_received")

        amount = request.data.get("amount")
        method = request.data.get("method", "cash")
        payment_date = request.data.get("payment_date")
        reference_number = request.data.get("reference_number", "")
        notes = request.data.get("notes", "")

        from apps.payments.services import record_onsite_payment
        from django.core.exceptions import ValidationError
        try:
            payment = record_onsite_payment(
                application=app,
                staff_user=request.user,
                amount=amount,
                method=method,
                payment_date=payment_date,
                reference_number=reference_number,
                notes=notes,
                payment_received=payment_received,
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        from apps.payments.serializers import PaymentSerializer
        return Response(
            PaymentSerializer(payment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="payment-summary")
    def payment_summary(self, request, pk=None):
        """Return fee and payment totals for this application."""
        app = self.get_object()
        from apps.payments.constants import PROTOTYPE_ADOPTION_FEE
        from apps.payments.models import Payment
        from apps.payments.serializers import PaymentSerializer
        from django.db.models import Sum
        from decimal import Decimal

        total = (
            app.payments.filter(status=Payment.Status.COMPLETED).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        is_paid = total >= PROTOTYPE_ADOPTION_FEE
        from apps.appointments.eligibility import onsite_visit_state
        visit = onsite_visit_state(app)
        eligible = (app.status == Application.Status.APPROVED) and visit["date_reached"] and is_paid

        return Response({
            "application_id": str(app.id),
            "adoption_fee": str(PROTOTYPE_ADOPTION_FEE),
            "total_paid": f"{total:.2f}",
            "is_fee_paid": is_paid,
            "can_record_payment": (
                app.status == Application.Status.APPROVED
                and visit["date_reached"]
                and not app.payments.filter(status=Payment.Status.COMPLETED).exists()
            ),
            "turnover_eligible": eligible,
            "onsite_visit": visit,
            "payments": PaymentSerializer(
                app.payments.all(), many=True, context=self.get_serializer_context()
            ).data,
        })

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        app = self.get_object()
        if app.status == Application.Status.APPROVED:
            return Response(
                {"error": "Please contact staff to cancel an approved adoption."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
