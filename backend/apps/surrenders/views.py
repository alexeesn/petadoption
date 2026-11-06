from django.db import transaction
from django.http import FileResponse, Http404
from rest_framework.generics import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.accounts.permissions import IsAdopter, IsStaff
from .models import SurrenderPhoto, SurrenderRequest
from .serializers import (IntakeSerializer, PhotoUploadSerializer, ReviewSerializer,
                          StaffSurrenderSerializer, SurrenderReadSerializer, SurrenderWriteSerializer)
from . import services


class VerifiedAccount(permissions.BasePermission):
    message = "Verify your email before accessing surrender requests."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_email_verified


class SurrenderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.CreateModelMixin, viewsets.GenericViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "species"]
    search_fields = ["pet_name", "breed"]
    ordering_fields = ["created_at", "intake_date", "pet_name"]

    def get_permissions(self):
        classes = [permissions.IsAuthenticated, VerifiedAccount]
        if self.action in ("review", "confirm_intake"):
            classes.append(IsStaff)
        elif self.action in ("create", "resubmit", "cancel"):
            classes.append(IsAdopter)
        return [cls() for cls in classes]

    def get_queryset(self):
        qs = SurrenderRequest.objects.select_related("owner").prefetch_related("photos", "history__actor")
        if self.request.user.is_staff_role or self.request.user.is_admin_role:
            return qs
        return qs.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.request.user.is_staff_role or self.request.user.is_admin_role:
            return StaffSurrenderSerializer
        return SurrenderReadSerializer

    def locked_object(self):
        obj = self.get_object()
        # Avoid joining nullable relations while acquiring PostgreSQL row locks.
        return SurrenderRequest.objects.select_for_update().get(pk=obj.pk)

    def create(self, request, *args, **kwargs):
        serializer = SurrenderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist("photos")
        if not 1 <= len(files) <= 5:
            raise ValidationError({"photos": "Upload 1 to 5 JPEG or PNG pet photos."})
        validated = []
        for file in files:
            photo = PhotoUploadSerializer(data={"image": file})
            photo.is_valid(raise_exception=True)
            validated.append(photo.validated_data["image"])
        saved = []
        try:
            with transaction.atomic():
                obj = serializer.save(owner=request.user)
                for file in validated:
                    photo = SurrenderPhoto.objects.create(request=obj, image=file)
                    saved.append(photo.image)
                services.record_event(obj, request.user, "submitted", note="Surrender request submitted for staff assessment.")
                services.notify_owner(obj, "Surrender request submitted", f"Your request for {obj.pet_name} is pending review. Keep the pet in your care until intake is confirmed.")
                services.notify_staff(obj, "New surrender request")
        except Exception:
            for file in saved:
                file.delete(save=False)
            raise
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def resubmit(self, request, pk=None):
        saved = []
        try:
            with transaction.atomic():
                obj = self.locked_object()
                if obj.status != SurrenderRequest.Status.NEEDS_INFORMATION:
                    raise ValidationError({"status": "Information can only be updated after staff requests it."})
                serializer = SurrenderWriteSerializer(obj, data=request.data)
                serializer.is_valid(raise_exception=True)
                files = request.FILES.getlist("photos")
                if len(files) > 5 or obj.photos.count() + len(files) > 10:
                    raise ValidationError({"photos": "Add up to 5 photos per update, with at most 10 photos per request."})
                validated = []
                for file in files:
                    photo = PhotoUploadSerializer(data={"image": file})
                    photo.is_valid(raise_exception=True)
                    validated.append(photo.validated_data["image"])
                serializer.save(status=SurrenderRequest.Status.SUBMITTED)
                for file in validated:
                    photo = SurrenderPhoto.objects.create(request=obj, image=file)
                    saved.append(photo.image)
                services.record_event(obj, request.user, "resubmitted", "needs_information", "Owner updated the requested information.")
                services.notify_owner(obj, "Surrender information updated", f"Your updated information for {obj.pet_name} has been sent for review.")
                services.notify_staff(obj, "Surrender information updated")
        except Exception:
            for file in saved:
                file.delete(save=False)
            raise
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        obj = self.locked_object()
        if obj.status in SurrenderRequest.TERMINAL_STATUSES:
            raise ValidationError({"status": "This request is already closed."})
        previous = obj.status
        obj.status, obj.intake_date, obj.intake_instructions = "cancelled", None, ""
        obj.save()
        services.record_event(obj, request.user, "cancelled", previous, "Owner cancelled the surrender request.")
        services.notify_owner(obj, "Surrender request cancelled", f"Your surrender request for {obj.pet_name} was cancelled.")
        services.notify_staff(obj, "Surrender request cancelled")
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def review(self, request, pk=None):
        obj = self.locked_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.review(obj, request.user, serializer.validated_data)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], url_path="confirm-intake")
    @transaction.atomic
    def confirm_intake(self, request, pk=None):
        obj = self.locked_object()
        serializer = IntakeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.data.get("confirmed") is not True:
            raise ValidationError({"confirmed": "Explicit handover confirmation is required."})
        services.confirm_intake(obj, request.user, serializer.validated_data)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["get"], url_path=r"photos/(?P<photo_id>[^/.]+)")
    def photo(self, request, pk=None, photo_id=None):
        obj = self.get_object()
        photo = get_object_or_404(SurrenderPhoto, request=obj, pk=photo_id)
        try:
            response = FileResponse(photo.image.open("rb"), content_type="image/png" if photo.image.name.endswith(".png") else "image/jpeg")
        except FileNotFoundError:
            raise Http404("Photo unavailable.")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
