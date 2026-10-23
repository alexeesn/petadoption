"""Shared Philippine-date gate for onsite payments and physical handover."""
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone


def philippine_today():
    return timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).date()


def confirmed_visit(application):
    return application.appointments.filter(status="confirmed").order_by("-requested_date").first()


def visit_state(appointment):
    if appointment is None:
        return {
            "appointment_date": None, "date_reached": False,
            "message": "A confirmed onsite visit appointment is required before recording payment or completing adoption.",
        }
    reached = appointment.requested_date <= philippine_today()
    return {
        "appointment_date": appointment.requested_date.isoformat(),
        "date_reached": reached,
        "message": "" if reached else (
            "Onsite payment and adoption completion are available on or after "
            f"{appointment.requested_date.isoformat()} (Philippine time). The appointment date has not arrived yet."
        ),
    }


def onsite_visit_state(application):
    return visit_state(confirmed_visit(application))


def require_onsite_visit(application):
    appointment = confirmed_visit(application)
    state = visit_state(appointment)
    if not state["date_reached"]:
        raise ValidationError(state["message"])
    return appointment


def onsite_payment_date(value, appointment):
    from apps.payments.models import Payment

    today = philippine_today()
    value = Payment._meta.get_field("payment_date").clean(value or today, None)
    if value < appointment.requested_date:
        raise ValidationError("Payment date cannot be before the confirmed appointment date.")
    if value > today:
        raise ValidationError("Payment date cannot be in the future (Philippine time).")
    return value
