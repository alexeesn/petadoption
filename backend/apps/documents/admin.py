from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("document_type", "application", "original_filename", "file_size", "created_at")
    list_filter = ("document_type",)
    search_fields = ("application__adopter__email", "original_filename")