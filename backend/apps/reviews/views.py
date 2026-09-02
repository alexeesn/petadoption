from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.utils import timezone
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer
from apps.accounts.permissions import IsStaff
from apps.notifications.models import create_notification


class ReviewListCreateView(generics.ListCreateAPIView):
    """Staff can list and create reviews."""
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ReviewCreateSerializer
        return ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related("application", "reviewer").all()
        application_id = self.request.query_params.get("application_id")
        if application_id:
            qs = qs.filter(application_id=application_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.applications.models import Application
        app = Application.objects.get(id=serializer.validated_data["application"])

        review = Review.objects.create(
            application=app,
            reviewer=request.user,
            decision=serializer.validated_data["decision"],
            internal_notes=serializer.validated_data.get("internal_notes", ""),
            adopter_visible_notes=serializer.validated_data.get("adopter_visible_notes", ""),
        )

        # Update application status based on decision
        decision = serializer.validated_data["decision"]

        # Applications enter review before a decision is applied. If the
        # application is still in a pre-review state (submitted, pending
        # documents, additional info requested), move it to under_review first.
        if app.status in ("submitted", "pending_documents", "additional_info_requested") \
                and app.can_transition_to("under_review"):
            app.status = "under_review"

        if decision == "approve" and app.can_transition_to("approved"):
            app.status = "approved"
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.pet.status = "pending"
            app.pet.save(update_fields=["status"])
        elif decision == "reject" and app.can_transition_to("rejected"):
            app.status = "rejected"
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
        elif decision == "request_info" and app.can_transition_to("additional_info_requested"):
            app.status = "additional_info_requested"
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
        app.save()

        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action="review_decision", model_name="Review",
            object_id=str(review.id), previous_value="", new_value=decision,
        )

        # Notify the adopter about the review decision
        decision_notifications = {
            "approve": (
                "Application Approved",
                f"Great news! Your application for {app.pet.name} has been approved.",
            ),
            "reject": (
                "Application Rejected",
                f"We regret to inform you that your application for {app.pet.name} has been rejected.",
            ),
            "request_info": (
                "Additional Information Required",
                f"We need more information for your application for {app.pet.name}. "
                f"{review.adopter_visible_notes}",
            ),
        }
        notif_title, notif_message = decision_notifications.get(
            decision,
            ("Application Update", f"Your application for {app.pet.name} has been updated."),
        )
        create_notification(
            user=app.adopter,
            title=notif_title,
            message=notif_message,
            notification_type="application",
            link=f"/applications/{app.id}",
        )

        return Response(ReviewSerializer(review, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ReviewDetailView(generics.RetrieveAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    queryset = Review.objects.select_related("application", "reviewer").all()
