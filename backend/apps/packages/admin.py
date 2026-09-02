from django.contrib import admin
from .models import AdoptionPackage


@admin.register(AdoptionPackage)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active")
    list_filter = ("is_active",)