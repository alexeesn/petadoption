from django.urls import path
from . import views

urlpatterns = [
    path("adoptions/", views.AdoptionReportView.as_view(), name="adoption-report"),
    path("pets/", views.PetInventoryReportView.as_view(), name="pet-inventory-report"),
    path("applications/", views.ApplicationReportView.as_view(), name="application-report"),
    path("payments/", views.PaymentReportView.as_view(), name="payment-report"),
    path("adopters/", views.AdopterReportView.as_view(), name="adopter-report"),
    path("health/", views.HealthReportView.as_view(), name="health-report"),
]