from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.adopters.models import AdopterProfile

User = get_user_model()

OTP_EXPIRY_MINUTES = 15
MAX_OTP_ATTEMPTS = 5
MAX_FAILED_LOGINS = 5


class BaseAPITestCase(TestCase):
    """Base test case with common helpers."""

    def setUp(self):
        self.client = APIClient()

    def create_user(self, email="adopter@example.com", password="TestPass123!",
                    role="adopter", verified=True, **kwargs):
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=kwargs.get("first_name", "Test"),
            last_name=kwargs.get("last_name", "User"),
            role=role,
        )
        if verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
        if role == "adopter":
            AdopterProfile.objects.get_or_create(user=user)
        return user

    def create_staff(self, **kwargs):
        kwargs.setdefault("role", "staff")
        return self.create_user(**kwargs)

    def create_admin(self, **kwargs):
        kwargs.setdefault("role", "admin")
        return self.create_user(**kwargs)

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return user

    def unauthenticate(self):
        self.client.credentials()

    def _now(self):
        return timezone.now()


class RegistrationTests(BaseAPITestCase):

    def test_register_success(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "new@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertTrue(user.otp)
        self.assertEqual(user.otp_type, "verify")
        self.assertIsNotNone(user.otp_created_at)
        self.assertEqual(user.otp_attempts, 0)

    def test_register_duplicate_email(self):
        self.create_user(email="new@example.com")
        resp = self.client.post("/api/auth/register/", {
            "email": "new@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_password_mismatch(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "new@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "Different123!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_email(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "not-an-email",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_weak_password(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "weak@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "123",
            "password_confirm": "123",
        })
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_fields(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "incomplete@example.com",
        })
        self.assertEqual(resp.status_code, 400)


class EmailVerificationTests(BaseAPITestCase):

    def _setup_user_with_otp(self, email="verify@example.com", otp="123456",
                             otp_type="verify"):
        user = self.create_user(email=email, verified=False)
        user.otp = otp
        user.otp_type = otp_type
        user.otp_created_at = self._now()
        user.otp_attempts = 0
        user.save()
        return user

    def test_verify_email_success(self):
        self._setup_user_with_otp()
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "verify@example.com",
            "otp": "123456",
        })
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(email="verify@example.com")
        self.assertTrue(user.is_email_verified)
        self.assertIsNone(user.otp)
        self.assertIsNone(user.otp_type)

    def test_verify_email_wrong_otp(self):
        self._setup_user_with_otp()
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "verify@example.com",
            "otp": "000000",
        })
        self.assertEqual(resp.status_code, 400)
        user = User.objects.get(email="verify@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.otp_attempts, 1)

    def test_verify_email_invalid_otp_format(self):
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "verify@example.com",
            "otp": "12345",
        })
        self.assertEqual(resp.status_code, 400)

    def test_verify_email_expired_otp(self):
        user = self._setup_user_with_otp()
        user.otp_created_at = self._now() - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        user.save(update_fields=["otp_created_at"])
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "verify@example.com",
            "otp": "123456",
        })
        self.assertEqual(resp.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_verify_email_otp_attempts_exceeded(self):
        user = self._setup_user_with_otp()
        for _ in range(MAX_OTP_ATTEMPTS - 1):
            resp = self.client.post("/api/auth/verify-email/", {
                "email": "verify@example.com",
                "otp": "000000",
            })
            self.assertEqual(resp.status_code, 400)
        # Next wrong attempt exhausts remaining → 429
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "verify@example.com",
            "otp": "000000",
        })
        self.assertEqual(resp.status_code, 429)

    def test_verify_email_already_verified(self):
        self.create_user(email="already@example.com", verified=True)
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "already@example.com",
            "otp": "123456",
        })
        self.assertEqual(resp.status_code, 200)

    def test_verify_email_nonexistent_user(self):
        resp = self.client.post("/api/auth/verify-email/", {
            "email": "nobody@example.com",
            "otp": "123456",
        })
        self.assertEqual(resp.status_code, 400)


class ResendOTPTests(BaseAPITestCase):

    def test_resend_otp_success(self):
        user = self.create_user(email="resend@example.com", verified=False)
        old_otp = "old_otp_value"
        user.otp = old_otp
        user.otp_attempts = 3
        user.save()
        resp = self.client.post("/api/auth/resend-otp/", {
            "email": "resend@example.com",
        })
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertNotEqual(user.otp, old_otp)
        self.assertEqual(user.otp_attempts, 0)
        self.assertIsNotNone(user.otp_created_at)

    def test_resend_otp_already_verified(self):
        self.create_user(email="verified@example.com", verified=True)
        resp = self.client.post("/api/auth/resend-otp/", {
            "email": "verified@example.com",
        })
        self.assertEqual(resp.status_code, 200)

    def test_resend_otp_nonexistent_email(self):
        resp = self.client.post("/api/auth/resend-otp/", {
            "email": "ghost@example.com",
        })
        self.assertEqual(resp.status_code, 200)


class LoginTests(BaseAPITestCase):

    def test_login_success(self):
        user = self.create_user(email="login@example.com")
        resp = self.client.post("/api/auth/login/", {
            "email": "login@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["user"]["email"], "login@example.com")

    def test_login_invalid_credentials(self):
        self.create_user(email="login@example.com")
        resp = self.client.post("/api/auth/login/", {
            "email": "login@example.com",
            "password": "WrongPass!",
        })
        self.assertEqual(resp.status_code, 401)

    def test_login_unverified(self):
        self.create_user(email="unverified@example.com", verified=False)
        resp = self.client.post("/api/auth/login/", {
            "email": "unverified@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 403)

    def test_login_lockout(self):
        user = self.create_user(email="lock@example.com")
        for _ in range(MAX_FAILED_LOGINS):
            resp = self.client.post("/api/auth/login/", {
                "email": "lock@example.com",
                "password": "WrongPass!",
            })
            self.assertEqual(resp.status_code, 401)
        resp = self.client.post("/api/auth/login/", {
            "email": "lock@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 423)

    def test_login_clears_failed_attempts_on_success(self):
        user = self.create_user(email="clear@example.com")
        user.failed_login_attempts = 3
        user.save(update_fields=["failed_login_attempts"])
        resp = self.client.post("/api/auth/login/", {
            "email": "clear@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)

    def test_login_nonexistent_email(self):
        resp = self.client.post("/api/auth/login/", {
            "email": "ghost@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 401)

    def test_login_disabled_account(self):
        user = self.create_user(email="disabled@example.com")
        user.is_active = False
        user.save(update_fields=["is_active"])
        resp = self.client.post("/api/auth/login/", {
            "email": "disabled@example.com",
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 403)


class LogoutTests(BaseAPITestCase):

    def test_logout_success(self):
        user = self.create_user(email="logout@example.com")
        self.authenticate(user)
        self.assertTrue(Token.objects.filter(user=user).exists())
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_logout_requires_auth(self):
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 403)


class ForgotPasswordTests(BaseAPITestCase):

    def test_forgot_password_success(self):
        self.create_user(email="forgot@example.com")
        resp = self.client.post("/api/auth/forgot-password/", {
            "email": "forgot@example.com",
        })
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(email="forgot@example.com")
        self.assertEqual(user.otp_type, "password_reset")
        self.assertIsNotNone(user.otp)
        self.assertEqual(user.otp_attempts, 0)

    def test_forgot_password_nonexistent_email(self):
        resp = self.client.post("/api/auth/forgot-password/", {
            "email": "ghost@example.com",
        })
        self.assertEqual(resp.status_code, 200)


class ResetPasswordTests(BaseAPITestCase):

    def _setup_user_with_reset_otp(self, email="reset@example.com", otp="123456"):
        user = self.create_user(email=email)
        user.otp = otp
        user.otp_type = "password_reset"
        user.otp_created_at = self._now()
        user.otp_attempts = 0
        user.save()
        return user

    def test_reset_password_success(self):
        self._setup_user_with_reset_otp()
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "123456",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(email="reset@example.com")
        self.assertTrue(user.check_password("NewStrongPass123!"))
        self.assertFalse(user.check_password("TestPass123!"))
        self.assertIsNone(user.otp)
        self.assertIsNone(user.otp_type)
        self.assertEqual(user.otp_attempts, 0)
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNone(user.locked_until)

    def test_reset_password_wrong_otp(self):
        user = self._setup_user_with_reset_otp()
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "000000",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.otp_attempts, 1)

    def test_reset_password_expired_otp(self):
        user = self._setup_user_with_reset_otp()
        user.otp_created_at = self._now() - timedelta(minutes=OTP_EXPIRY_MINUTES + 1)
        user.save(update_fields=["otp_created_at"])
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "123456",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_otp_attempts_exceeded(self):
        user = self._setup_user_with_reset_otp()
        for _ in range(MAX_OTP_ATTEMPTS - 1):
            resp = self.client.post("/api/auth/reset-password/", {
                "email": "reset@example.com",
                "otp": "000000",
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            })
            self.assertEqual(resp.status_code, 400)
        # Next wrong attempt exhausts remaining → 429
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "000000",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 429)

    def test_reset_password_mismatch(self):
        self._setup_user_with_reset_otp()
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "123456",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "DifferentPass456!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_reset_password_clears_lockout(self):
        user = self._setup_user_with_reset_otp()
        user.failed_login_attempts = 4
        user.locked_until = self._now() + timedelta(minutes=10)
        user.save()
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "reset@example.com",
            "otp": "123456",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertIsNone(user.locked_until)

    def test_reset_password_nonexistent_user(self):
        resp = self.client.post("/api/auth/reset-password/", {
            "email": "ghost@example.com",
            "otp": "123456",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)


class ChangePasswordTests(BaseAPITestCase):

    def test_change_password_success(self):
        user = self.create_user(email="change@example.com")
        self.authenticate(user)
        old_token = Token.objects.get(user=user).key
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "TestPass123!",
            "new_password": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.data)
        new_token = resp.data["token"]
        # Old token should be deleted; new token issued
        self.assertFalse(Token.objects.filter(key=old_token).exists())
        self.assertTrue(Token.objects.filter(user=user).exists())
        self.assertNotEqual(old_token, new_token)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))

    def test_change_password_wrong_old(self):
        user = self.create_user(email="change@example.com")
        self.authenticate(user)
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "WrongOldPass!",
            "new_password": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 400)

    def test_change_password_weak_new(self):
        user = self.create_user(email="change@example.com")
        self.authenticate(user)
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "TestPass123!",
            "new_password": "123",
        })
        self.assertEqual(resp.status_code, 400)

    def test_change_password_requires_auth(self):
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "TestPass123!",
            "new_password": "NewStrongPass123!",
        })
        self.assertEqual(resp.status_code, 403)


class ProfileTests(BaseAPITestCase):

    def test_get_own_profile(self):
        user = self.create_user(email="profile@example.com")
        self.authenticate(user)
        resp = self.client.get("/api/auth/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["email"], "profile@example.com")

    def test_profile_requires_auth(self):
        resp = self.client.get("/api/auth/profile/")
        self.assertEqual(resp.status_code, 403)

    def test_update_own_profile(self):
        user = self.create_user(email="profile@example.com")
        self.authenticate(user)
        resp = self.client.patch("/api/auth/profile/", {
            "first_name": "Updated",
            "last_name": "Name",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.last_name, "Name")

    def test_profile_readonly_fields(self):
        user = self.create_user(email="profile@example.com")
        self.authenticate(user)
        resp = self.client.patch("/api/auth/profile/", {
            "email": "hacked@example.com",
            "role": "admin",
            "is_email_verified": True,
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "profile@example.com")
        self.assertEqual(user.role, "adopter")