from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("application", "adopter", "pet", "requested_date", "status")
    list_filter = ("status",)