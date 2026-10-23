from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsStaff
from .models import RescheduleRequest
from .serializers import RescheduleRequestSerializer
from .services import review_reschedule


class RescheduleRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RescheduleRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [permissions.IsAuthenticated(), IsStaff()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = RescheduleRequest.objects.select_related(
            "appointment", "application__adopter", "application__pet", "reviewed_by"
        )
        if self.request.user.is_adopter:
            queryset = queryset.filter(application__adopter=self.request.user)
        if self.request.query_params.get("application"):
            application_id = serializers.UUIDField().run_validation(self.request.query_params["application"])
            queryset = queryset.filter(application_id=application_id)
        if self.request.query_params.get("status"):
            queryset = queryset.filter(status=self.request.query_params["status"])
        return queryset

    def decide(self, request, approve):
        instance = self.get_object()
        try:
            instance = review_reschedule(
                instance, request.user, approve=approve,
                reason=request.data.get("reason"), confirmed=request.data.get("confirmed"),
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self.decide(request, True)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self.decide(request, False)
