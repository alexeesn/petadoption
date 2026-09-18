"""
Adoption application lifecycle email helpers.

Follows the same delivery pattern as apps/accounts/emails.py: Django's
send_mail with a branded HTML template rendered from
backend/templates/emails/ and a plain-text fallback.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Application

logger = logging.getLogger(__name__)


def send_application_approval_email(application) -> None:
    """
    Notify the adopter that their adoption application was approved.

    The email tells the adopter to log in to the PawConnect adopter portal
    and select an available appointment date for their onsite visit.
    Appointment scheduling itself happens inside the adopter portal — this
    email is only a notification and never contains an appointment date.

    Must only be called on a real transition into Application.Status.APPROVED;
    callers guard this with Application.can_transition_to("approved"), and a
    status check here keeps it safe even if a future caller forgets.
    """
    if application.status != Application.Status.APPROVED:
        logger.warning(
            "Skipping approval email for application %s in status '%s'.",
            application.id, application.status,
        )
        return

    adopter = application.adopter
    adopter_name = adopter.full_name or adopter.first_name or "there"
    application_url = f"{settings.ADOPTER_PORTAL_URL}/applications/{application.id}"

    subject = "Your PawConnect adoption application has been approved"
    context = {
        "adopter_name": adopter_name,
        "pet_name": application.pet.name,
        "application_id": str(application.id),
        "application_url": application_url,
    }

    plain_message = (
        f"Hello {adopter_name},\n\n"
        f"Your adoption application for {application.pet.name} has been approved.\n"
        f"Application reference: {application.id}\n\n"
        f"Please log in to your PawConnect account to continue the adoption "
        f"process and select an available appointment date for your onsite visit.\n\n"
        f"View your application: {application_url}\n\n"
        f"Thank you,\n"
        f"PawConnect"
    )

    try:
        html_message = render_to_string("emails/application_approved.html", context)
    except Exception as exc:
        logger.warning("Failed to render application_approved.html: %s", exc)
        html_message = None

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[adopter.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.error("Failed to send approval email to %s: %s", adopter.email, exc)
