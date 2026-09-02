"""
URL configuration for pet-adoption backend.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/adopters/", include("apps.adopters.urls")),
    path("api/pets/", include("apps.pets.urls")),
    path("api/applications/", include("apps.applications.urls")),
    path("api/documents/", include("apps.documents.urls")),
    path("api/reviews/", include("apps.reviews.urls")),
    path("api/packages/", include("apps.packages.urls")),
    path("api/health-records/", include("apps.health.urls")),
    path("api/adoptions/", include("apps.adoptions.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/audit/", include("apps.audit.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)