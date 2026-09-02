from rest_framework import serializers
import os
from .models import Document

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


class DocumentSerializer(serializers.ModelSerializer):
    application_pet = serializers.CharField(source="application.pet.name", read_only=True)
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True, default=None)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "application", "application_pet", "document_type", "file",
            "original_filename", "content_type", "file_size", "notes",
            "uploaded_by", "uploaded_by_email", "download_url", "created_at",
        ]
        read_only_fields = [
            "id", "original_filename", "content_type", "file_size",
            "uploaded_by", "uploaded_by_email", "download_url", "created_at",
        ]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        return request.build_absolute_uri(f"/api/documents/{obj.id}/download/")

    def validate_file(self, value):
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError("File size exceeds 10MB limit.")
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(f"File type '{ext}' is not allowed.")
        allowed = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                   "png": "image/png", "doc": "application/msword",
                   "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   "txt": "text/plain"}
        expected_mime = allowed.get(ext.lstrip("."))
        content_type = getattr(value, "content_type", None)
        if content_type and expected_mime and content_type != expected_mime:
            raise serializers.ValidationError(f"MIME type '{content_type}' does not match file extension.")
        return value