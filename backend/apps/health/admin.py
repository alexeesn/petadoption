from django.contrib import admin
from .models import HealthRecord, Vaccination


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "veterinarian_name", "record_date")
    list_filter = ("record_date",)


@admin.register(Vaccination)
class VaccinationAdmin(admin.ModelAdmin):
    list_display = ("vaccine_name", "pet", "date_administered", "next_due_date")
    list_filter = ("vaccine_name",)