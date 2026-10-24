from django.db import transaction
from rest_framework import viewsets, permissions, serializers, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import HealthRecord, Vaccination
from .serializers import HealthRecordSerializer, VaccinationSerializer
from apps.accounts.permissions import IsStaff
from apps.filters import RecordScopeFilter
from apps.pets.models import Pet
from apps.pets.serializers import PetListSerializer


class HealthRecordViewSet(viewsets.ModelViewSet):
    queryset = HealthRecord.objects.select_related("pet", "created_by").order_by(
        "-created_at", "-id"
    )
    serializer_class = HealthRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter, RecordScopeFilter]
    filterset_fields = ["pet"]
    scope_status_field = "pet__status"
    active_statuses = Pet.ACTIVE_STATUSES

    @transaction.atomic
    def perform_create(self, serializer):
        # Serialize new records for this pet, including requests made from a
        # stale dropdown. Keep existing dated medical history intact.
        pet = Pet.objects.select_for_update().get(pk=serializer.validated_data["pet"].pk)
        if HealthRecord.objects.filter(pet=pet).exists():
            raise serializers.ValidationError({
                "pet": "This pet already has a health record. Use Edit to update it."
            })
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="eligible-pets")
    def eligible_pets(self, request):
        """Staff-only choices, checked against all records, not one list page."""
        pets = Pet.objects.filter(health_records__isnull=True).prefetch_related(
            "images"
        ).order_by("-created_at", "-id")
        page = self.paginate_queryset(pets)
        if page is not None:
            return self.get_paginated_response(
                PetListSerializer(page, many=True, context=self.get_serializer_context()).data
            )
        return Response(PetListSerializer(
            pets, many=True, context=self.get_serializer_context()
        ).data)


class VaccinationViewSet(viewsets.ModelViewSet):
    queryset = Vaccination.objects.select_related("pet").all()
    serializer_class = VaccinationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
