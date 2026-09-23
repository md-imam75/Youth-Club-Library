"""accounts/urls.py"""

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('membership/', views.membership_view, name='membership'),
    path('membership/apply/<int:plan_id>/', views.apply_membership_view, name='apply_membership'),
    path('delete-account/', views.delete_account_view, name='delete_account'),
]
