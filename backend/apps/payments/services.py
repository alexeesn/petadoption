"""
Service module for on-site adoption fee payment handling.
"""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.notifications.models import create_notification
from .constants import PROTOTYPE_ADOPTION_FEE
from .models import Payment


@transaction.atomic
def record_onsite_payment(
    application,
    staff_user,
    amount=None,
    method="cash",
    payment_date=None,
    reference_number="",
    notes="",
    payment_received=None,
):
    """Record an on-site adoption fee payment.

    Enforces the business rules:
    - Only staff or administrators can record payments for an adoption.
    - Staff can record a payment only after actually receiving the money.
    - A successfully recorded on-site payment has status 'completed'.
    - Records exactly the server-defined one-time prototype fee.
    - Locks the application before checking for an existing completed payment.
    - Generates a permanent unique receipt identifier (receipt_number).
    - Never trusts client-supplied status or transaction IDs.
    - Persists audit log and notifies the adopter.
    """
    if not staff_user or not (staff_user.is_staff_role or staff_user.is_admin_role):
        raise PermissionDenied("Only staff or administrators can record payments.")

    if payment_received is not True:
        raise ValidationError("Payment can only be recorded after receiving the money.")

    if amount is not None:
        try:
            supplied_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError("Invalid payment amount format.")
        if not supplied_amount.is_finite() or supplied_amount != PROTOTYPE_ADOPTION_FEE:
            raise ValidationError(f"The required onsite payment is exactly ₱{PROTOTYPE_ADOPTION_FEE:.2f}.")

    from apps.applications.models import Application

    # Both HTTP payment actions use this service. Serializing on their shared
    # application row prevents concurrent requests from collecting twice, even
    # before the first Payment row exists. Historical duplicates stay intact.
    application = Application.objects.select_for_update().get(pk=application.pk)
    if application.payments.filter(status=Payment.Status.COMPLETED).exists():
        raise ValidationError("A completed payment already exists for this application.")
    if application.status != Application.Status.APPROVED:
        raise ValidationError("Only an approved application can receive an onsite payment.")

    if not payment_date:
        payment_date = timezone.localdate()

    payment = Payment(
        application=application,
        amount=PROTOTYPE_ADOPTION_FEE,
        method=method or "cash",
        status=Payment.Status.COMPLETED,
        payment_date=payment_date,
        reference_number=reference_number or "",
        notes=notes or "",
        processed_by=staff_user,
    )
    payment.full_clean()
    payment.save()

    AuditLog.objects.create(
        user=staff_user,
        action="payment_created",
        model_name="Payment",
        object_id=str(payment.id),
        previous_value="",
        new_value=f"₱{payment.amount} completed (onsite {payment.receipt_number})",
    )

    create_notification(
        user=application.adopter,
        title="Payment Confirmed",
        message=f"An on-site payment of ₱{payment.amount} has been received and confirmed (Receipt: {payment.receipt_number}).",
        notification_type="payment",
        link=f"/payments/{payment.id}",
    )

    return payment
