from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "amount", "method", "status", "receipt_number")
    list_filter = ("status", "method")