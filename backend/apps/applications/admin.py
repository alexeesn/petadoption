from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "adopter", "pet", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("adopter__email", "pet__name")

    def get_changeform_initial_data(self, request):
        """Default new applications to 'submitted' in the admin form.

        The draft → submitted auto-advance lives in Application.save(), but
        the admin form is pre-populated with 'draft' (the model field default)
        unless we override it here.  Defaulting to 'submitted' ensures the
        admin path matches the API path and never leaves applications stuck
        in draft.
        """
        return {"status": Application.Status.SUBMITTED}
