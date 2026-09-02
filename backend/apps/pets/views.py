from rest_framework import viewsets, permissions, filters
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from .models import Pet, PetImage
from .serializers import PetSerializer, PetListSerializer, PetImageSerializer
from apps.accounts.permissions import IsStaff


class PetViewSet(viewsets.ModelViewSet):
    """CRUD for pets. Public list/retrieve, staff-only create/update/delete."""
    queryset = Pet.objects.prefetch_related("images").all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "species", "gender", "size", "is_vaccinated", "is_neutered"]
    search_fields = ["name", "breed", "description"]
    ordering_fields = ["name", "age_months", "created_at", "adoption_fee"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsStaff()]

    def get_serializer_class(self):
        if self.action == "list":
            return PetListSerializer
        return PetSerializer

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        new_status = serializer.validated_data.get("status", old_status)
        serializer.save()
        if old_status != new_status:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=self.request.user,
                action="pet_status_change",
                model_name="Pet",
                object_id=str(instance.id),
                previous_value=old_status,
                new_value=new_status,
            )


class PetImageViewSet(viewsets.ModelViewSet):
    """CRUD for pet images. Staff only."""
    serializer_class = PetImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return PetImage.objects.filter(pet_id=self.kwargs.get("pet_pk"))

    def perform_create(self, serializer):
        serializer.save(pet_id=self.kwargs.get("pet_pk"))
