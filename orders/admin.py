"""
orders/admin.py
"""

from django.contrib import admin
from django.utils import timezone
from .models import Order


def mark_paid(modeladmin, request, queryset):
    queryset.update(payment_status='Paid')
mark_paid.short_description = '✅ Mark selected orders as Paid'


def mark_failed(modeladmin, request, queryset):
    queryset.update(payment_status='Failed')
mark_failed.short_description = '❌ Mark selected orders as Failed'


def mark_returned(modeladmin, request, queryset):
    for order in queryset.filter(order_type='Borrow', returned_at__isnull=True):
        order.mark_returned()
mark_returned.short_description = '📦 Mark selected borrows as Returned'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'book', 'order_type', 'delivery_option',
        'total_cost', 'payment_method', 'payment_status', 'is_overdue', 'created_at'
    ]
    list_filter = ['order_type', 'payment_status', 'payment_method', 'delivery_option']
    search_fields = ['user__email', 'user__username', 'book__title', 'transaction_id']
    readonly_fields = ['created_at', 'book_price', 'delivery_cost']
    actions = [mark_paid, mark_failed, mark_returned]
    ordering = ['-created_at']

    @admin.display(boolean=True, description='Overdue?')
    def is_overdue(self, obj):
        return obj.is_overdue
