from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "reviewer", "decision", "created_at")
    list_filter = ("decision",)