from django.urls import path
from . import views

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", views.UnreadCountView.as_view(), name="notification-unread-count"),
    path("mark-all-read/", views.MarkAllAsReadView.as_view(), name="notification-mark-all-read"),
    path("<uuid:pk>/", views.NotificationDetailView.as_view(), name="notification-detail"),
    path("<uuid:pk>/read/", views.MarkAsReadView.as_view(), name="notification-mark-read"),
]