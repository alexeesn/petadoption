from rest_framework import viewsets, permissions, filters, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .models import Pet, PetImage
from .serializers import PetSerializer, PetListSerializer, PetImageSerializer
from apps.accounts.permissions import IsStaff


class PetViewSet(viewsets.ModelViewSet):
    """CRUD for pets. Public list/retrieve, staff-only create/update/delete.

    On create, any uploaded `images` files are saved as PetImage records
    for the new pet (the first uploaded image becomes the primary image).
    """
    queryset = Pet.objects.prefetch_related("images").all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "species", "gender", "size", "is_vaccinated", "is_neutered"]
    search_fields = ["name", "breed", "description"]
    ordering_fields = ["name", "age_years", "created_at", "adoption_fee"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsStaff()]

    def get_serializer_class(self):
        if self.action == "list":
            return PetListSerializer
        return PetSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            pet = serializer.save()
            # Reuse the existing PetImageSerializer so uploads go through the
            # same DRF ImageField validation (image content check via Pillow,
            # size limits) as the existing per-image endpoint.
            for i, image in enumerate(request.FILES.getlist("images")):
                image_serializer = PetImageSerializer(
                    data={"image": image}, context=self.get_serializer_context()
                )
                image_serializer.is_valid(raise_exception=True)
                image_serializer.save(pet=pet, is_primary=(i == 0))
        output = PetSerializer(pet, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

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
    """CRUD for the images of one pet. Staff only.

    This is the existing photo architecture reused by the Staff Portal
    "Edit Pet" screen: adding a photo POSTs a single file here, while removing
    a photo DELETEs only that image, so untouched photos are never affected.

    The first image of a pet is always its primary image, and deleting the
    primary image promotes the next remaining photo so a pet that still has
    photos is never left without a primary one.
    """
    serializer_class = PetImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    parser_classes = [MultiPartParser, FormParser]

    def get_pet(self):
        return get_object_or_404(Pet, pk=self.kwargs.get("pet_pk"))

    def get_queryset(self):
        return PetImage.objects.filter(pet_id=self.kwargs.get("pet_pk"))

    def perform_create(self, serializer):
        pet = self.get_pet()
        is_primary = not PetImage.objects.filter(pet=pet).exists()
        serializer.save(pet=pet, is_primary=is_primary)

    def perform_destroy(self, instance):
        pet_id = instance.pet_id
        was_primary = instance.is_primary
        instance.delete()
        if was_primary:
            next_image = (
                PetImage.objects.filter(pet_id=pet_id).order_by("created_at").first()
            )
            if next_image:
                next_image.is_primary = True
                next_image.save(update_fields=["is_primary"])
