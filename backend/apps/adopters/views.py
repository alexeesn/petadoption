from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdopterProfile, IdentityVerification
from .serializers import (
    AdopterProfileSerializer,
    AdopterProfileUpdateSerializer,
    IdentityVerificationSerializer,
    IdentityVerificationStaffSerializer,
    IdentityVerificationSubmitSerializer,
    IdentityVerificationReviewSerializer,
)
from apps.accounts.permissions import IsAdopter, IsStaff
from apps.audit.models import AuditLog
from apps.notifications.models import create_notification


class AdopterProfileView(generics.RetrieveUpdateAPIView):
    """Adopter can view/edit own profile. Staff can view all."""
    serializer_class = AdopterProfileSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdopter()]

    def get_object(self):
        profile, _ = AdopterProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return AdopterProfileSerializer
        return AdopterProfileUpdateSerializer

    def update(self, request, *args, **kwargs):
        """
        Persist changes using the write serializer, then return the full read
        serializer so the response always includes computed fields such as
        profile_is_complete, user_email, user_name, and timestamps.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write_serializer = AdopterProfileUpdateSerializer(
            instance, data=request.data, partial=partial
        )
        write_serializer.is_valid(raise_exception=True)
        self.perform_update(write_serializer)
        read_serializer = AdopterProfileSerializer(instance, context={"request": request})
        return Response(read_serializer.data)


class AdopterListView(generics.ListAPIView):
    """Staff/Admin: list all adopters."""
    serializer_class = AdopterProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_queryset(self):
        return AdopterProfile.objects.select_related("user").order_by("user__email").all()


class AdopterDetailView(generics.RetrieveAPIView):
    """Staff/Admin: view a specific adopter."""
    serializer_class = AdopterProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    queryset = AdopterProfile.objects.select_related("user").order_by("user__email").all()


# ---------------------------------------------------------------------------
# Identity Verification views — adopter-facing
# ---------------------------------------------------------------------------

class IdentityVerificationView(APIView):
    """
    GET  /api/adopters/verification/  — returns the adopter's own verification record.
    POST /api/adopters/verification/  — submit or resubmit verification files + consent.

    Security:
    - Only the authenticated adopter can access their own record.
    - The adopter cannot change status to 'verified'; that is staff-only.
    - Files are validated for type (PDF / image) and size server-side.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdopter]
    parser_classes = [MultiPartParser, FormParser]

    def _get_or_create_iv(self, request):
        profile, _ = AdopterProfile.objects.get_or_create(user=request.user)
        iv, _ = IdentityVerification.objects.get_or_create(profile=profile)
        return iv

    def get(self, request):
        iv = self._get_or_create_iv(request)
        serializer = IdentityVerificationSerializer(iv, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        iv = self._get_or_create_iv(request)

        # Validate the submission payload
        serializer = IdentityVerificationSubmitSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Prevent replacing files while a review is already pending
        if iv.status == IdentityVerification.Status.PENDING_REVIEW:
            return Response(
                {"error": "Your documents are currently under review and cannot be replaced."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Clear old files if replacing (rejected or not_submitted)
        if iv.combined_pdf:
            iv.combined_pdf.delete(save=False)
        if iv.selfie_with_id:
            iv.selfie_with_id.delete(save=False)

        iv.combined_pdf = data["combined_pdf"]
        iv.selfie_with_id = data["selfie_with_id"]
        iv.privacy_consent = True
        iv.consent_given_at = timezone.now()
        iv.submitted_at = timezone.now()
        iv.status = IdentityVerification.Status.PENDING_REVIEW
        # Clear a previous rejection reason on resubmission
        iv.rejection_reason = ""
        # Reset reviewer info (new review cycle)
        iv.reviewed_by = None
        iv.reviewed_at = None
        iv.save()

        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action="verification_submitted",
            model_name="IdentityVerification",
            object_id=str(iv.id),
            previous_value={"status": iv.status},
            new_value={"status": IdentityVerification.Status.PENDING_REVIEW},
        )

        # Notify staff that a new verification submission arrived
        from apps.accounts.models import User
        for staff_user in User.objects.filter(role__in=["staff", "admin"], is_active=True):
            create_notification(
                user=staff_user,
                title="Identity Verification Submitted",
                message=(
                    f"{request.user.full_name or request.user.email} has submitted "
                    "identity verification documents for review."
                ),
                notification_type="verification",
                link=f"/verification-requests/{iv.id}",
            )

        # Notify adopter
        create_notification(
            user=request.user,
            title="Verification Documents Submitted",
            message=(
                "Your identity documents have been submitted and are pending review. "
                "You will be notified of the outcome."
            ),
            notification_type="verification",
            link="/profile",
        )

        read_serializer = IdentityVerificationSerializer(iv, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_200_OK)


class IdentityVerificationDownloadView(APIView):
    """
    GET /api/adopters/verification/download/<field>/

    Secure download of the authenticated adopter's own verification file.
    Never returns a public static URL.
    <field> must be one of: combined_pdf, selfie_with_id
    """
    permission_classes = [permissions.IsAuthenticated, IsAdopter]

    ALLOWED_FIELDS = {"combined_pdf", "selfie_with_id"}

    def get(self, request, field):
        if field not in self.ALLOWED_FIELDS:
            return Response({"error": "Invalid field."}, status=status.HTTP_404_NOT_FOUND)
        profile = get_object_or_404(AdopterProfile, user=request.user)
        iv = get_object_or_404(IdentityVerification, profile=profile)
        file_obj = getattr(iv, field)
        if not file_obj:
            return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            file_handle = file_obj.open("rb")
            response = FileResponse(file_handle)
            response["Content-Disposition"] = f'attachment; filename="{field}.pdf"'
            return response
        except Exception:
            return Response({"error": "File could not be opened."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Identity Verification views — staff-facing
# ---------------------------------------------------------------------------

class IdentityVerificationAdminListView(generics.ListAPIView):
    """
    GET /api/adopters/verification-requests/

    Staff/Admin: list all verification requests.
    Supports ?status=pending_review|verified|rejected|not_submitted filtering.
    """
    serializer_class = IdentityVerificationStaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["submitted_at", "status", "created_at"]
    ordering = ["-submitted_at"]

    def get_queryset(self):
        qs = IdentityVerification.objects.select_related(
            "profile__user", "reviewed_by"
        ).exclude(status=IdentityVerification.Status.NOT_SUBMITTED)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class IdentityVerificationAdminDetailView(APIView):
    """
    GET  /api/adopters/verification-requests/<uuid>/  — full verification detail.
    POST /api/adopters/verification-requests/<uuid>/review/  — approve or reject.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get(self, request, pk):
        iv = get_object_or_404(
            IdentityVerification.objects.select_related("profile__user", "reviewed_by"),
            pk=pk,
        )
        serializer = IdentityVerificationStaffSerializer(iv, context={"request": request})
        return Response(serializer.data)

    def post(self, request, pk):
        """Review action: approve or reject the verification request."""
        iv = get_object_or_404(
            IdentityVerification.objects.select_related("profile__user"),
            pk=pk,
        )

        if iv.status not in (
            IdentityVerification.Status.PENDING_REVIEW,
        ):
            return Response(
                {
                    "error": (
                        f"Cannot review a verification in '{iv.status}' status. "
                        "Only 'pending_review' submissions can be reviewed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IdentityVerificationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        rejection_reason = serializer.validated_data.get("rejection_reason", "").strip()

        old_status = iv.status

        if decision == "approve":
            iv.status = IdentityVerification.Status.VERIFIED
            iv.rejection_reason = ""
        else:
            iv.status = IdentityVerification.Status.REJECTED
            iv.rejection_reason = rejection_reason

        iv.reviewed_by = request.user
        iv.reviewed_at = timezone.now()
        iv.save()

        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action="verification_reviewed",
            model_name="IdentityVerification",
            object_id=str(iv.id),
            previous_value={"status": old_status},
            new_value={"status": iv.status, "decision": decision},
        )

        # Notify the adopter of the outcome
        adopter_user = iv.profile.user
        if decision == "approve":
            create_notification(
                user=adopter_user,
                title="Identity Verification Approved",
                message=(
                    "Your identity has been verified! You can now submit adoption applications."
                ),
                notification_type="verification",
                link="/profile",
            )
        else:
            create_notification(
                user=adopter_user,
                title="Identity Verification Requires Correction",
                message=(
                    f"Your identity verification was not approved. Reason: {rejection_reason} "
                    "Please correct the issue and resubmit."
                ),
                notification_type="verification",
                link="/profile",
            )

        read_serializer = IdentityVerificationStaffSerializer(iv, context={"request": request})
        return Response(read_serializer.data)


class IdentityVerificationAdminFileDownloadView(APIView):
    """
    GET /api/adopters/verification-requests/<uuid>/download/<field>/

    Staff-only secure file download for a specific verification record.
    <field> must be one of: combined_pdf, selfie_with_id

    Files are NEVER served through public static URLs.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    ALLOWED_FIELDS = {"combined_pdf", "selfie_with_id"}

    def get(self, request, pk, field):
        if field not in self.ALLOWED_FIELDS:
            return Response({"error": "Invalid field."}, status=status.HTTP_404_NOT_FOUND)
        iv = get_object_or_404(IdentityVerification, pk=pk)
        file_obj = getattr(iv, field)
        if not file_obj:
            return Response({"error": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            file_handle = file_obj.open("rb")
            ext = "pdf" if field == "combined_pdf" else "jpg"
            response = FileResponse(file_handle)
            response["Content-Disposition"] = (
                f'attachment; filename="{iv.profile.user.email}_{field}.{ext}"'
            )
            return response
        except Exception:
            return Response(
                {"error": "File could not be opened."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
