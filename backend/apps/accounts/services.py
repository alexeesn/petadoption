"""
Google OAuth verification service.

The Google Identity Services (GIS) JavaScript SDK obtains an ID token on the
client and sends it to our backend. We NEVER trust user-provided profile data —
the ID token is verified server-side using Google's public certificates so the
`email`, `name`, and `email_verified` claims come directly from Google.
"""
import logging

from django.conf import settings

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    """Raised when Google OAuth validation fails."""


def verify_google_id_token(credential: str) -> dict:
    """
    Verify a Google ID token and return its verified claims.

    Raises `GoogleAuthError` when the token is missing, invalid, expired,
    malformed, or issued for the wrong audience/client.
    """
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise GoogleAuthError("Google authentication is not configured.")

    if not credential or not isinstance(credential, str):
        raise GoogleAuthError("Invalid Google credential.")

    try:
        info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # Occurs when the token is invalid, expired, or for the wrong audience.
        logger.warning("Google ID token verification failed: %s", exc)
        raise GoogleAuthError("The Google sign-in could not be verified.") from exc
    except Exception as exc:  # noqa: BLE001 - any Google verification failure is safe to swallow
        logger.warning("Unexpected Google token verification error: %s", exc)
        raise GoogleAuthError("The Google sign-in could not be verified.") from exc

    if not info.get("email_verified"):
        raise GoogleAuthError("Your Google email is not verified.")

    email = (info.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("Google did not provide a valid email address.")

    return {
        "email": email,
        "first_name": (info.get("given_name") or "").strip(),
        "last_name": (info.get("family_name") or "").strip(),
    }
