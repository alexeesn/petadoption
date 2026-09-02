"""
Django settings for running tests without requiring PostgreSQL superuser.
Uses in-memory SQLite so tests can run in CI/development without DB privileges.
The application itself still targets PostgreSQL in dev/production.
"""

from .development import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"