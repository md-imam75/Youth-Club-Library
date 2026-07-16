"""
accounts/models.py

Models: CustomUser, MembershipPlan, UserMembership
"""

import random
import string
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


def generate_membership_id():
    """Generate a unique membership ID in the format YCL + 9 digits."""
    digits = ''.join(random.choices(string.digits, k=9))
    return f'YCL{digits}'


class CustomUser(AbstractUser):
    """
    Extended user model with unique email and additional profile fields.
    Email is used as the primary login identifier via django-allauth.
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, verbose_name='Phone Number')
    address = models.TextField(blank=True, verbose_name='Delivery Address')
    profile_image = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        verbose_name='Profile Photo'
    )
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full if full else self.username

    @property
    def active_membership(self):
        """Returns the user's membership if it is currently Active, else None."""
        try:
            m = self.membership
            if m.status == 'Active' and m.expires_at and m.expires_at > timezone.now():
                return m
        except UserMembership.DoesNotExist:
            pass
        return None

    @property
    def has_active_membership(self):
        return self.active_membership is not None


class MembershipPlan(models.Model):
    """
    Library membership tiers displayed as pricing cards.
    characteristics is a JSON list of feature strings, e.g.:
    ["Borrow up to 3 books", "Priority reservations", ...]
    """
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30, help_text='Duration of membership in days')
    characteristics = models.JSONField(
        default=list,
        help_text='JSON list of feature strings shown on pricing card'
    )
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text='Highlight as most popular')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price']
        verbose_name = 'Membership Plan'
        verbose_name_plural = 'Membership Plans'

    def __str__(self):
        return f'{self.name} — ৳{self.price}'

    @property
    def duration_label(self):
        if self.duration_days == 30:
            return '1 Month'
        elif self.duration_days == 90:
            return '3 Months'
        elif self.duration_days == 180:
            return '6 Months'
        elif self.duration_days == 365:
            return '1 Year'
        return f'{self.duration_days} Days'


class UserMembership(models.Model):
    """
    Links a user to a membership plan. One membership per user at a time.
    Admin reviews Pending memberships and manually sets them Active.
    """
    STATUS_PENDING = 'Pending'
    STATUS_ACTIVE = 'Active'
    STATUS_EXPIRED = 'Expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    PAYMENT_OFFLINE = 'Offline'
    PAYMENT_BKASH = 'bKash'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_OFFLINE, 'Offline'),
        (PAYMENT_BKASH, 'bKash'),
    ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='membership'
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memberships'
    )
    unique_membership_id = models.CharField(
        max_length=12,
        unique=True,
        default=generate_membership_id,
        editable=False
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_OFFLINE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text='Admin notes')

    class Meta:
        verbose_name = 'User Membership'
        verbose_name_plural = 'User Memberships'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.unique_membership_id} — {self.user.get_full_name()} [{self.status}]'

    def activate(self):
        """Called by admin action to activate a pending membership."""
        self.status = self.STATUS_ACTIVE
        self.activated_at = timezone.now()
        if self.plan:
            self.expires_at = timezone.now() + timedelta(days=self.plan.duration_days)
        self.save()

    def check_expiry(self):
        """Mark expired if past expiry date."""
        if self.status == self.STATUS_ACTIVE and self.expires_at and timezone.now() > self.expires_at:
            self.status = self.STATUS_EXPIRED
            self.save()

    @property
    def days_remaining(self):
        if self.expires_at and self.status == self.STATUS_ACTIVE:
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return 0
