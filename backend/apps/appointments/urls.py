from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .reschedule_views import RescheduleRequestViewSet

router = DefaultRouter()
router.register(r"reschedule-requests", RescheduleRequestViewSet, basename="reschedule-request")
router.register(r"", views.AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("", include(router.urls)),
]
