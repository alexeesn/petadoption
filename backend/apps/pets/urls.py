from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"", views.PetViewSet, basename="pet")
router.register(r"(?P<pet_pk>[^/.]+)/images", views.PetImageViewSet, basename="pet-image")

urlpatterns = [
    path("", include(router.urls)),
]
