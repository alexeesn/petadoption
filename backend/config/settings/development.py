"""
Django development settings.
"""

from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Email backend for development: uses SMTP if configured in .env, otherwise console
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if (os.environ.get("SMTP_HOST") or os.environ.get("EMAIL_HOST_USER") or os.environ.get("SMTP_USERNAME"))
    else "django.core.mail.backends.console.EmailBackend",
)

# CORS - allow all localhost origins for development
CORS_ALLOW_ALL_ORIGINS = True
