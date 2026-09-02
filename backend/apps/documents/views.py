from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Document
from .serializers import DocumentSerializer
from apps.notifications.models import create_notification


class DocumentPermissionMixin:
    """Documents are private. Only the owning adopter or staff can access."""
    def get_queryset(self):
        user = self.request.user
        if user.is_staff_role or user.is_admin_role:
            return Document.objects.select_related("application", "application__pet", "uploaded_by").all()
        return Document.objects.filter(application__adopter=user).select_related(
            "application", "application__pet", "uploaded_by"
        )

    def check_object_permission(self, obj):
        user = self.request.user
        if user.is_staff_role or user.is_admin_role:
            return True
        return obj.application.adopter == user


class DocumentListCreateView(DocumentPermissionMixin, generics.ListCreateAPIView):
    """List/create documents. The mixin provides the owner/staff queryset filter."""
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        application_id = self.request.query_params.get("application_id")
        if application_id:
            qs = qs.filter(application_id=application_id)
        return qs

    def perform_create(self, serializer):
        from apps.applications.models import Application
        application_id = self.request.data.get("application")
        if not application_id:
            raise serializers.ValidationError({"application": "Application is required."})
        app = get_object_or_404(Application, id=application_id)
        user = self.request.user
        if not (user.is_staff_role or user.is_admin_role or app.adopter == user):
            raise PermissionDenied("You do not have access to this application.")
        file_obj = self.request.FILES.get("file")
        doc = serializer.save(
            application=app,
            uploaded_by=user,
            original_filename=file_obj.name if file_obj else "",
            content_type=getattr(file_obj, "content_type", "") if file_obj else "",
            file_size=file_obj.size if file_obj else 0,
        )
        # Notify staff when an adopter uploads a document
        if user.is_adopter:
            from apps.accounts.models import User
            for staff_user in User.objects.filter(role__in=["staff", "admin"], is_active=True):
                create_notification(
                    user=staff_user,
                    title="New Document Uploaded",
                    message=f"A new {app.pet.name} application document has been uploaded.",
                    notification_type="document",
                    link=f"/documents/{doc.id}",
                )
        # Notify the adopter that a staff member added a document
        else:
            create_notification(
                user=app.adopter,
                title="Document Added",
                message=f"A document has been added to your application for {app.pet.name}.",
                notification_type="document",
                link=f"/documents/{doc.id}",
            )


class DocumentDeleteView(DocumentPermissionMixin, generics.DestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self.check_object_permission(instance):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentDownloadView(APIView, DocumentPermissionMixin):
    """Authorized file download - never expose documents via public static URLs."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)
        if not self.check_object_permission(doc):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        file_handle = doc.file.open()
        response = FileResponse(file_handle)
        response["Content-Disposition"] = f'attachment; filename="{doc.original_filename or doc.file.name}"'
        return response