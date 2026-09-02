from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "adopter", "pet", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("adopter__email", "pet__name")
