"""
Django production settings.
"""

from .base import *

DEBUG = False

# SMTP email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USERNAME", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")

# CORS restricted
CORS_ALLOW_ALL_ORIGINS = False
