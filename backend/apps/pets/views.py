from rest_framework import viewsets, permissions, filters, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .models import Pet, PetImage
from .serializers import PetSerializer, PetListSerializer, PetImageSerializer, RecordPetDeathSerializer, CorrectPetDeathSerializer
from apps.accounts.permissions import IsStaff, IsAdmin
from apps.filters import RecordScopeFilter


class PetViewSet(viewsets.ModelViewSet):
    """CRUD for pets. Public list/retrieve, staff-only create/update/delete.

    On create, any uploaded `images` files are saved as PetImage records
    for the new pet (the first uploaded image becomes the primary image).
    """
    queryset = Pet.objects.prefetch_related("images").all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter, RecordScopeFilter]
    active_statuses = Pet.ACTIVE_STATUSES
    filterset_fields = {
        "status": ["exact"], "species": ["exact"], "gender": ["exact"],
        "size": ["exact"], "is_vaccinated": ["exact"], "is_neutered": ["exact"],
        "weight_kg": ["gte", "lte"],
    }
    search_fields = ["name", "breed", "description"]
    ordering_fields = ["name", "age_years", "age_months", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.action == "list" and not (user.is_authenticated and (user.is_staff_role or user.is_admin_role)):
            qs = qs.exclude(status=Pet.Status.DECEASED)
        return qs

    def get_permissions(self):
        if self.action == "correct_death":
            return [permissions.IsAuthenticated(), IsAdmin()]
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

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        Pet.objects.select_for_update().get(pk=obj.pk)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="record-death")
    def record_death(self, request, pk=None):
        obj = self.get_object()
        serializer = RecordPetDeathSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.data.get("confirmed") is not True:
            raise ValidationError({"confirmed": "Confirm that the pet died while in center custody."})
        from .lifecycle import record_pet_death
        data = dict(serializer.validated_data)
        data.pop("confirmed")
        obj = record_pet_death(obj.pk, request.user, data)
        return Response(PetSerializer(obj, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="correct-death")
    def correct_death(self, request, pk=None):
        obj = self.get_object()
        serializer = CorrectPetDeathSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.data.get("confirmed") is not True:
            raise ValidationError({"confirmed": "Explicit confirmation of this correction is required."})
        from .lifecycle import correct_pet_death
        obj = correct_pet_death(obj.pk, request.user, serializer.validated_data["reason"])
        return Response(PetSerializer(obj, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({"detail": "This pet is linked to retained records. Mark it inactive instead of deleting it."})


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
