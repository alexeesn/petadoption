from django.urls import path
from . import views

urlpatterns = [
    path("", views.DocumentListCreateView.as_view(), name="document-list"),
    path("<uuid:pk>/", views.DocumentDeleteView.as_view(), name="document-delete"),
    path("<uuid:pk>/download/", views.DocumentDownloadView.as_view(), name="document-download"),
]