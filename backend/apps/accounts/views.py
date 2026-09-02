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

from .serializers import (
    RegisterSerializer, VerifyEmailSerializer, ResendOTPSerializer,
    LoginSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
    UserSerializer, ChangePasswordSerializer, generate_otp,
)

User = get_user_model()
logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 15
MAX_OTP_ATTEMPTS = 5
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 30


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
        try:
            send_mail(
                subject="Verify your email - Pet Adoption",
                message=f"Your verification code is: {otp}\nIt expires in {OTP_EXPIRY_MINUTES} minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}")
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
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.otp_attempts = 0
        user.save(update_fields=["otp", "otp_created_at", "otp_attempts"])
        try:
            send_mail(
                subject="Verify your email - Pet Adoption",
                message=f"Your verification code is: {otp}\nIt expires in {OTP_EXPIRY_MINUTES} minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}")
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
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.otp_type = "password_reset"
        user.otp_attempts = 0
        user.save(update_fields=["otp", "otp_created_at", "otp_type", "otp_attempts"])
        try:
            send_mail(
                subject="Password Reset - Pet Adoption",
                message=f"Your password reset code is: {otp}\nIt expires in {OTP_EXPIRY_MINUTES} minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")
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
