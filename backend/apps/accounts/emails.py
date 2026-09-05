"""
Email rendering and delivery utilities for accounts authentication.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_verification_email(user, otp: str, expiry_minutes: int = 10) -> None:
    """
    Send a branded verification OTP email with responsive HTML and plain-text fallback.
    """
    subject = "Verify your email - Pet Adoption"
    context = {
        "first_name": user.first_name,
        "otp_code": otp,
        "expiry_minutes": expiry_minutes,
    }

    plain_message = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"Thank you for joining Pet Adoption!\n"
        f"Your verification code is: {otp}\n"
        f"It expires in {expiry_minutes} minutes.\n\n"
        f"If you did not register for an account, please ignore this email."
    )

    try:
        html_message = render_to_string("emails/verify_email.html", context)
    except Exception as exc:
        logger.warning("Failed to render verify_email.html: %s", exc)
        html_message = None

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", user.email, exc)


def send_password_reset_email(user, otp: str, expiry_minutes: int = 10) -> None:
    """
    Send a branded password reset OTP email with responsive HTML and plain-text fallback.
    """
    subject = "Password Reset - Pet Adoption"
    context = {
        "first_name": user.first_name,
        "otp_code": otp,
        "expiry_minutes": expiry_minutes,
    }

    plain_message = (
        f"Hi {user.first_name or 'there'},\n\n"
        f"We received a request to reset your password for Pet Adoption.\n"
        f"Your password reset code is: {otp}\n"
        f"It expires in {expiry_minutes} minutes.\n\n"
        f"If you did not request this, please ignore this email."
    )

    try:
        html_message = render_to_string("emails/password_reset.html", context)
    except Exception as exc:
        logger.warning("Failed to render password_reset.html: %s", exc)
        html_message = None

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.error("Failed to send password reset email to %s: %s", user.email, exc)
