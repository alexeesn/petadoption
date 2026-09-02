import uuid
from django.db import models
from django.conf import settings


def document_upload_path(instance, filename):
    """Generate a secure filename for uploaded documents (no user-controlled paths)."""
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    safe_name = f"{uuid.uuid4().hex}"
    return f"documents/{instance.application_id}/{safe_name}.{ext}"


class Document(models.Model):
    """Private document attached to an application."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=50, choices=[
        ("identification", "Identification"),
        ("proof_of_address", "Proof of Address"),
        ("income_proof", "Income Proof"),
        ("vet_reference", "Veterinary Reference"),
        ("personal_reference", "Personal Reference"),
        ("home_photos", "Home Photos"),
        ("lease_agreement", "Lease Agreement"),
        ("other", "Other"),
    ])
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Document {self.document_type} for app {self.application_id}"