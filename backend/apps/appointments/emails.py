"""
Appointment decision email helpers (approve / reject the requested date).

Follows the same delivery pattern as apps/applications/emails.py and
apps/accounts/emails.py: Django's send_mail with a branded HTML template
rendered from backend/templates/emails/ plus a plain-text fallback.

Only these two appointment emails belong to the appointment decision. The
adoption application approval email stays in apps/applications/emails.py and
is untouched.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.defaultfilters import date as date_filter
from django.template.loader import render_to_string

from .models import Appointment

logger = logging.getLogger(__name__)

APPROVED_SUBJECT = "Your PawConnect appointment has been approved"
REJECTED_SUBJECT = "Your PawConnect appointment needs a new date"


def _adopter_name(appointment) -> str:
    adopter = appointment.adopter
    return adopter.full_name or adopter.first_name or "there"


def _display_date(value) -> str:
    """Render the appointment date from the database in a readable form."""
    return date_filter(value, "F j, Y")


def _send(subject, plain_message, html_template, context, recipient) -> None:
    """Deliver one branded email through the shared Django email backend."""
    try:
        html_message = render_to_string(html_template, context)
    except Exception as exc:
        logger.warning("Failed to render %s: %s", html_template, exc)
        html_message = None

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception as exc:
        logger.error("Failed to send '%s' to %s: %s", subject, recipient, exc)


def send_appointment_approved_email(appointment) -> None:
    """
    Notify the adopter that their requested onsite visit date was approved.

    Must only be called on a real transition into Appointment.Status.CONFIRMED;
    callers guard this with Appointment.can_transition_to("confirmed"), and the
    status check here keeps it safe even if a future caller forgets — which is
    also what keeps a repeated approve request from emailing twice.
    """
    if appointment.status != Appointment.Status.CONFIRMED:
        logger.warning(
            "Skipping appointment approval email for %s in status '%s'.",
            appointment.id, appointment.status,
        )
        return

    adopter_name = _adopter_name(appointment)
    appointment_date = _display_date(appointment.requested_date)
    application_url = (
        f"{settings.ADOPTER_PORTAL_URL}/applications/{appointment.application_id}"
    )

    plain_message = (
        f"Hello {adopter_name},\n\n"
        f"Your appointment for the adoption of {appointment.pet.name} has been approved.\n\n"
        f"Appointment Date:\n"
        f"{appointment_date}\n\n"
        f"You may now visit the center on the approved date for your onsite adoption process.\n\n"
        f"View your application: {application_url}\n\n"
        f"Thank you,\n"
        f"PawConnect"
    )

    _send(
        APPROVED_SUBJECT,
        plain_message,
        "emails/appointment_approved.html",
        {
            "adopter_name": adopter_name,
            "pet_name": appointment.pet.name,
            "appointment_date": appointment_date,
            "application_id": str(appointment.application_id),
            "application_url": application_url,
        },
        appointment.adopter.email,
    )


def send_appointment_rejected_email(appointment) -> None:
    """
    Notify the adopter that their requested date was not approved, including
    the reason recorded by staff/admin.

    The adoption application itself is untouched by an appointment-date
    rejection, so the email makes that explicit and points the adopter back to
    the portal to choose another date.

    Must only be called on a real transition into Appointment.Status.REJECTED;
    callers guard this with Appointment.can_transition_to("rejected") plus the
    required-reason validation, and the checks here keep a repeated reject
    request from emailing twice.
    """
    if appointment.status != Appointment.Status.REJECTED:
        logger.warning(
            "Skipping appointment rejection email for %s in status '%s'.",
            appointment.id, appointment.status,
        )
        return

    reason = (appointment.rejection_reason or "").strip()
    if not reason:
        logger.warning(
            "Skipping appointment rejection email for %s: no rejection reason.",
            appointment.id,
        )
        return

    adopter_name = _adopter_name(appointment)
    appointment_date = _display_date(appointment.requested_date)
    application_url = (
        f"{settings.ADOPTER_PORTAL_URL}/applications/{appointment.application_id}"
    )

    plain_message = (
        f"Hello {adopter_name},\n\n"
        f"Your requested appointment date for the adoption of {appointment.pet.name} "
        f"could not be approved.\n\n"
        f"Requested Date:\n"
        f"{appointment_date}\n\n"
        f"Reason:\n"
        f"{reason}\n\n"
        f"Please log in to your PawConnect account and choose another available "
        f"appointment date.\n\n"
        f"Your adoption application is still approved.\n\n"
        f"Choose another date: {application_url}\n\n"
        f"Thank you,\n"
        f"PawConnect"
    )

    _send(
        REJECTED_SUBJECT,
        plain_message,
        "emails/appointment_rejected.html",
        {
            "adopter_name": adopter_name,
            "pet_name": appointment.pet.name,
            "appointment_date": appointment_date,
            "rejection_reason": reason,
            "application_id": str(appointment.application_id),
            "application_url": application_url,
        },
        appointment.adopter.email,
    )