from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.adopters.models import AdopterProfile

from .emails import send_verification_email, send_password_reset_email
from .services import verify_google_id_token, GoogleAuthError
from .serializers import (
    RegisterSerializer, VerifyEmailSerializer, ResendOTPSerializer,
    LoginSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
    UserSerializer, ChangePasswordSerializer, GoogleAuthSerializer, generate_otp,
)

User = get_user_model()
logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 15
MAX_OTP_ATTEMPTS = 5
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 30
OTP_RESEND_COOLDOWN_SECONDS = 60


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.otp_type = "verify"
        user.otp_attempts = 0
        user.save(update_fields=["otp", "otp_created_at", "otp_type", "otp_attempts"])
        send_verification_email(user, otp, expiry_minutes=OTP_EXPIRY_MINUTES)
        return Response(
            {"message": "Registration successful. Please check your email for verification code."},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp_code = serializer.validated_data["otp"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_email_verified:
            return Response({"message": "Email already verified."}, status=status.HTTP_200_OK)
        if user.otp != otp_code:
            user.otp_attempts += 1
            user.save(update_fields=["otp_attempts"])
            remaining = MAX_OTP_ATTEMPTS - user.otp_attempts
            if remaining <= 0:
                return Response({"error": "Too many failed attempts. Please request a new code."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            return Response({"error": f"Invalid OTP. {remaining} attempts remaining."}, status=status.HTTP_400_BAD_REQUEST)
        if user.otp_created_at and (timezone.now() - user.otp_created_at) > timedelta(minutes=OTP_EXPIRY_MINUTES):
            return Response({"error": "OTP has expired. Please request a new code."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_email_verified = True
        user.otp = None
        user.otp_created_at = None
        user.otp_type = None
        user.otp_attempts = 0
        user.save(update_fields=["is_email_verified", "otp", "otp_created_at", "otp_type", "otp_attempts"])
        return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If the email exists, a new code has been sent."}, status=status.HTTP_200_OK)
        if user.is_email_verified:
            return Response({"message": "Email already verified."}, status=status.HTTP_200_OK)
        # Resend cooldown: do not allow sending again too frequently.
        if user.otp_created_at:
            elapsed = (timezone.now() - user.otp_created_at).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1
                return Response(
                    {"error": f"Please wait {wait} second(s) before requesting a new code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.otp_attempts = 0
        user.save(update_fields=["otp", "otp_created_at", "otp_attempts"])
        send_verification_email(user, otp, expiry_minutes=OTP_EXPIRY_MINUTES)
        return Response({"message": "If the email exists, a new code has been sent."}, status=status.HTTP_200_OK)



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        if user.locked_until and timezone.now() < user.locked_until:
            remaining = (user.locked_until - timezone.now()).seconds // 60 + 1
            return Response({"error": f"Account locked. Try again in {remaining} minute(s)."}, status=status.HTTP_423_LOCKED)
        if not user.check_password(password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_LOGINS:
                user.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            user.save(update_fields=["failed_login_attempts", "locked_until"])
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_email_verified:
            return Response({"error": "Please verify your email before logging in."}, status=status.HTTP_403_FORBIDDEN)
        if not user.is_active:
            return Response({"error": "Account is disabled."}, status=status.HTTP_403_FORBIDDEN)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until"])
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If the email exists, a reset code has been sent."}, status=status.HTTP_200_OK)
        # Cooldown (per password-reset flow) prevents email spam.
        if user.otp_created_at and user.otp_type == "password_reset":
            elapsed = (timezone.now() - user.otp_created_at).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1
                return Response(
                    {"error": f"Please wait {wait} second(s) before requesting another reset code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.otp_type = "password_reset"
        user.otp_attempts = 0
        user.save(update_fields=["otp", "otp_created_at", "otp_type", "otp_attempts"])
        send_password_reset_email(user, otp, expiry_minutes=OTP_EXPIRY_MINUTES)
        return Response({"message": "If the email exists, a reset code has been sent."}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp_code = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
        if user.otp != otp_code or user.otp_type != "password_reset":
            user.otp_attempts += 1
            user.save(update_fields=["otp_attempts"])
            remaining = MAX_OTP_ATTEMPTS - user.otp_attempts
            if remaining <= 0:
                return Response({"error": "Too many failed attempts. Please request a new code."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            return Response({"error": f"Invalid OTP. {remaining} attempts remaining."}, status=status.HTTP_400_BAD_REQUEST)
        if user.otp_created_at and (timezone.now() - user.otp_created_at) > timedelta(minutes=OTP_EXPIRY_MINUTES):
            return Response({"error": "OTP has expired. Please request a new code."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.otp = None
        user.otp_created_at = None
        user.otp_type = None
        user.otp_attempts = 0
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save()
        return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        Token.objects.filter(user=request.user).delete()
        token, _ = Token.objects.get_or_create(user=request.user)
        return Response({"message": "Password changed successfully.", "token": token.key}, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """
    Authenticate (or create) a user using a verified Google ID token.

    The ID token is verified server-side. Existing users are matched by their
    verified Google email. New Google accounts are created as adopters only —
    staff/admin privileges are never granted automatically. Existing RBAC is
    preserved.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]

        try:
            claims = verify_google_id_token(credential)
        except GoogleAuthError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        email = claims["email"]

        # Match an existing user by verified email. Avoids duplicate accounts.
        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            # New Google account → create as an adopter (never staff/admin).
            user = User.objects.create_user(
                email=email,
                password=None,
                first_name=claims["first_name"],
                last_name=claims["last_name"],
                role=User.Role.ADOPTER,
                is_email_verified=True,
                is_active=True,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            AdopterProfile.objects.get_or_create(user=user)
        else:
            # Existing account — ensure the verified email state stays correct.
            if not user.is_email_verified:
                user.is_email_verified = True
                user.save(update_fields=["is_email_verified"])

        # Disabled / locked accounts must never be able to sign in.
        if not user.is_active:
            return Response({"error": "Account is disabled."}, status=status.HTTP_403_FORBIDDEN)
        if user.locked_until and timezone.now() < user.locked_until:
            return Response({"error": "Account is temporarily locked. Try again later."}, status=status.HTTP_423_LOCKED)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until"])

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_200_OK)
