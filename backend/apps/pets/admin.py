from django.contrib import admin
from .models import Pet, PetImage


class PetImageInline(admin.TabularInline):
    model = PetImage
    extra = 0


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "breed", "status", "age_months", "created_at")
    list_filter = ("status", "species", "gender", "size")
    search_fields = ("name", "breed", "description")
    inlines = [PetImageInline]
