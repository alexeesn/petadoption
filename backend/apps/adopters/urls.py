from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.AdopterProfileView.as_view(), name="adopter-profile"),
    path("", views.AdopterListView.as_view(), name="adopter-list"),
    path("<uuid:pk>/", views.AdopterDetailView.as_view(), name="adopter-detail"),
]
