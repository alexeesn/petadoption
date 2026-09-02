from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Payment
from .serializers import PaymentSerializer
from apps.accounts.permissions import IsStaff, IsAdopter
from apps.notifications.models import create_notification


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_adopter:
            return Payment.objects.filter(application__adopter=user).select_related(
                "application", "application__adopter", "package", "processed_by"
            )
        return Payment.objects.select_related(
            "application", "application__adopter", "package", "processed_by"
        ).all()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsStaff()]

    def perform_create(self, serializer):
        payment = serializer.save(processed_by=self.request.user)
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=self.request.user, action="payment_created", model_name="Payment",
            object_id=str(payment.id), previous_value="", new_value=f"₱{payment.amount} {payment.status}",
        )
        create_notification(
            user=payment.application.adopter,
            title="Payment Requested",
            message=f"A payment of ₱{payment.amount} has been recorded for your application.",
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
            # Notify the adopter about payment status change
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