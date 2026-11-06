from django.urls import path
from . import views

urlpatterns = [
    # Adopter-facing profile endpoints
    path("profile/", views.AdopterProfileView.as_view(), name="adopter-profile"),
    # Adopter-facing identity verification endpoints
    path(
        "verification/",
        views.IdentityVerificationView.as_view(),
        name="identity-verification",
    ),
    path(
        "verification/download/<str:field>/",
        views.IdentityVerificationDownloadView.as_view(),
        name="identity-verification-download",
    ),
    # Staff-facing endpoints (list + detail + file download)
    path(
        "verification-requests/",
        views.IdentityVerificationAdminListView.as_view(),
        name="verification-request-list",
    ),
    path(
        "verification-requests/<uuid:pk>/",
        views.IdentityVerificationAdminDetailView.as_view(),
        name="verification-request-detail",
    ),
    path(
        "verification-requests/<uuid:pk>/review/",
        views.IdentityVerificationAdminDetailView.as_view(),
        name="verification-request-review",
    ),
    path(
        "verification-requests/<uuid:pk>/download/<str:field>/",
        views.IdentityVerificationAdminFileDownloadView.as_view(),
        name="verification-request-download",
    ),
    # Staff list / detail adopters (must come last to avoid swallowing uuid paths)
    path("", views.AdopterListView.as_view(), name="adopter-list"),
    path("<uuid:pk>/", views.AdopterDetailView.as_view(), name="adopter-detail"),
]
