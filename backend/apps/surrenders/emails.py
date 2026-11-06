"""Branded surrender updates with the existing plain-text delivery fallback."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_surrender_update_email(recipient, title, plain_message, context):
    try:
        html_message = render_to_string("emails/surrender_update.html", context)
    except Exception:
        logger.exception("Unable to render surrender update email; using plain text")
        html_message = None
    try:
        send_mail(subject=title, message=plain_message, html_message=html_message,
                  from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[recipient])
    except Exception:
        logger.exception("Unable to send surrender update email")
