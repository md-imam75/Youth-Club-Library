"""
accounts/admin.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import CustomUser, MembershipPlan, UserMembership


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'get_full_name', 'is_staff', 'has_active_membership', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('phone', 'address', 'profile_image', 'date_of_birth', 'bio')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profile', {'fields': ('email', 'first_name', 'last_name', 'phone')}),
    )

    @admin.display(boolean=True, description='Active Membership')
    def has_active_membership(self, obj):
        return obj.has_active_membership


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_label', 'is_popular', 'is_active', 'sort_order']
    list_editable = ['is_popular', 'is_active', 'sort_order']
    list_filter = ['is_active', 'is_popular']
    search_fields = ['name']


def activate_memberships(modeladmin, request, queryset):
    """Admin action to bulk-activate pending memberships."""
    for membership in queryset.filter(status=UserMembership.STATUS_PENDING):
        membership.activate()
    modeladmin.message_user(request, f'{queryset.count()} membership(s) activated.')
activate_memberships.short_description = '✅ Activate selected memberships'


def expire_memberships(modeladmin, request, queryset):
    queryset.update(status=UserMembership.STATUS_EXPIRED)
expire_memberships.short_description = '❌ Mark selected memberships as Expired'


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display = [
        'unique_membership_id', 'user', 'plan', 'status',
        'payment_method', 'transaction_id', 'expires_at', 'days_remaining'
    ]
    list_filter = ['status', 'payment_method', 'plan']
    search_fields = ['unique_membership_id', 'user__email', 'user__username', 'transaction_id']
    readonly_fields = ['unique_membership_id', 'created_at', 'activated_at']
    actions = [activate_memberships, expire_memberships]
    ordering = ['-created_at']

    @admin.display(description='Days Remaining')
    def days_remaining(self, obj):
        return obj.days_remaining
