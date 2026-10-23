"""
Django settings for running tests without requiring PostgreSQL superuser.
Uses in-memory SQLite so tests can run in CI/development without DB privileges.
The application itself still targets PostgreSQL in dev/production.
"""

from .development import *

# A developer's local demo switch must not change the normal test workflow.
NO_SHOW_DEMO_ENABLED = False

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
