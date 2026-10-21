from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .constants import PROTOTYPE_ADOPTION_FEE
from .models import Payment
from .serializers import PaymentSerializer
from .services import record_onsite_payment
from apps.accounts.permissions import IsStaff, IsAdopter
from apps.notifications.models import create_notification


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_adopter:
            qs = Payment.objects.filter(application__adopter=user)
        else:
            qs = Payment.objects.all()
        qs = qs.select_related(
            "application", "application__adopter", "package", "processed_by"
        )
        # Optional filter so the onsite transaction for a single application can
        # be loaded from the staff application detail page.
        application_id = self.request.query_params.get("application")
        if application_id:
            qs = qs.filter(application_id=application_id)
        return qs

    def get_permissions(self):
        if self.action in ["list", "retrieve", "fee"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsStaff()]

    @action(detail=False, methods=["get"], url_path="fee")
    def fee(self, request):
        """Return the central prototype adoption fee."""
        return Response({"adoption_fee": str(PROTOTYPE_ADOPTION_FEE)})

    @action(detail=False, methods=["post"], url_path="record-onsite")
    def record_onsite(self, request):
        """Dedicated staff action for recording on-site payments."""
        if not (request.user.is_staff_role or request.user.is_admin_role):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        app_id = request.data.get("application")
        if not app_id:
            return Response({"application": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        from apps.applications.models import Application
        try:
            app = Application.objects.get(id=app_id)
        except (Application.DoesNotExist, ValueError):
            return Response({"application": ["Invalid application ID."]}, status=status.HTTP_400_BAD_REQUEST)

        payment_received = request.data.get("payment_received", True)
        if payment_received is False or payment_received == "false":
            return Response(
                {"error": "Payment can only be recorded after receiving the money."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = request.data.get("amount")
        method = request.data.get("method", "cash")
        payment_date = request.data.get("payment_date")
        reference_number = request.data.get("reference_number", "")
        notes = request.data.get("notes", "")

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
                payment_received=True,
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PaymentSerializer(payment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        payment = serializer.save(processed_by=self.request.user)
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=self.request.user, action="payment_created", model_name="Payment",
            object_id=str(payment.id), previous_value="", new_value=f"₱{payment.amount} {payment.status}",
        )
        notification_title = (
            "Payment Confirmed" if payment.status == Payment.Status.COMPLETED else "Payment Requested"
        )
        notification_msg = (
            f"Your payment of ₱{payment.amount} has been confirmed. Thank you!"
            if payment.status == Payment.Status.COMPLETED
            else f"A payment of ₱{payment.amount} has been recorded for your application."
        )
        create_notification(
            user=payment.application.adopter,
            title=notification_title,
            message=notification_msg,
            notification_type="payment",
            link=f"/payments/{payment.id}",
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_status = instance.status
        response = super().update(request, *args, **kwargs)
        new_status = instance.status
        if old_status != new_status:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user, action="payment_status_change", model_name="Payment",
                object_id=str(instance.id), previous_value=old_status, new_value=new_status,
            )
            payment_status_messages = {
                "completed": f"Your payment of ₱{instance.amount} has been confirmed. Thank you!",
                "failed": f"Your payment of ₱{instance.amount} has failed. Please try again.",
                "refunded": f"Your payment of ₱{instance.amount} has been refunded.",
                "pending": f"Your payment of ₱{instance.amount} is now pending.",
            }
            create_notification(
                user=instance.application.adopter,
                title=f"Payment {new_status.replace('_', ' ').title()}",
                message=payment_status_messages.get(
                    new_status, f"Your payment status has been updated to '{new_status}'."
                ),
                notification_type="payment",
                link=f"/payments/{instance.id}",
            )
        return response
