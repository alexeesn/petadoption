from django.contrib import admin
from .models import AdopterProfile


@admin.register(AdopterProfile)
class AdopterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "state", "phone_number", "created_at")
    search_fields = ("user__email", "city", "state")
