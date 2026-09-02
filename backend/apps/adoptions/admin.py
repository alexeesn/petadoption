from django.contrib import admin
from .models import AdoptionRecord


@admin.register(AdoptionRecord)
class AdoptionRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "adopter", "status", "adoption_date", "completed_date")
    list_filter = ("status",)