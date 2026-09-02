"""
Django development settings.
"""

from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Console email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS - allow all localhost origins for development
CORS_ALLOW_ALL_ORIGINS = True
