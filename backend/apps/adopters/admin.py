from django.contrib import admin
from .models import AdopterProfile, IdentityVerification


@admin.register(AdopterProfile)
class AdopterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "state", "phone_number", "created_at")
    search_fields = ("user__email", "city", "state")


@admin.register(IdentityVerification)
class IdentityVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "profile", "status", "submitted_at", "reviewed_by", "reviewed_at"
    )
    list_filter = ("status",)
    search_fields = ("profile__user__email",)
    readonly_fields = (
        "id", "profile", "submitted_at", "consent_given_at",
        "reviewed_by", "reviewed_at", "created_at", "updated_at",
    )
