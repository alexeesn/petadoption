from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Register the primary health-record viewset at the router root so that
# /api/health-records/ maps to HealthRecordViewSet (list/create) and
# /api/health-records/<uuid:pk>/ maps to record detail/update/delete.
router = DefaultRouter()
router.register(r"", views.HealthRecordViewSet, basename="health-record")

# Vaccinations are exposed as an explicit path (listed before the router so the
# root viewset's <pk> pattern does not swallow the "vaccinations" segment).
vaccination_actions = views.VaccinationViewSet.as_view({
    "get": "list",
    "post": "create",
})
vaccination_detail_actions = views.VaccinationViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})

urlpatterns = [
    path("vaccinations/", vaccination_actions, name="vaccination-list"),
    path("vaccinations/<uuid:pk>/", vaccination_detail_actions, name="vaccination-detail"),
    path("", include(router.urls)),
]