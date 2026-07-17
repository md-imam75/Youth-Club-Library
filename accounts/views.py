"""
accounts/views.py
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CustomUser, MembershipPlan, UserMembership
from .forms import ProfileUpdateForm, MembershipApplicationForm
from orders.models import Order
from catalog.models import BookRequest


@login_required
def dashboard_view(request):
    """User dashboard: membership status, order history, profile form."""
    user = request.user

    # Check/update expiry status
    try:
        membership = user.membership
        membership.check_expiry()
    except UserMembership.DoesNotExist:
        membership = None

    # Order history
    orders = Order.objects.filter(user=user).select_related('book').order_by('-created_at')
    bought_orders = orders.filter(order_type='Buy')
    borrowed_orders = orders.filter(order_type='Borrow')

    # Book Requests
    book_requests = BookRequest.objects.filter(user=user).prefetch_related('items').order_by('-created_at')

    # Profile form
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileUpdateForm(instance=user)

    context = {
        'membership': membership,
        'bought_orders': bought_orders,
        'borrowed_orders': borrowed_orders,
        'book_requests': book_requests,
        'form': form,
        'page_title': 'My Dashboard',
    }
    return render(request, 'accounts/dashboard.html', context)


def membership_view(request):
    """Display all membership plans as pricing cards. Public — no login required."""
    plans = MembershipPlan.objects.filter(is_active=True)

    # Check existing membership only for logged-in users
    current = None
    if request.user.is_authenticated:
        try:
            current = request.user.membership
            current.check_expiry()
        except UserMembership.DoesNotExist:
            current = None

    context = {
        'plans': plans,
        'current_membership': current,
        'page_title': 'Membership Plans',
        'steps': [
            'Choose a plan',
            'Make payment via bKash or offline cash',
            'Admin verifies your payment within 24 hours',
            'Borrow any book from our catalog — free!',
        ],
    }
    return render(request, 'accounts/membership.html', context)


@login_required
def apply_membership_view(request, plan_id):
    """Handle membership application form submission."""
    plan = get_object_or_404(MembershipPlan, id=plan_id, is_active=True)
    user = request.user

    # Check if already has a non-expired membership
    try:
        existing = user.membership
        if existing.status in ('Pending', 'Active'):
            messages.warning(
                request,
                f'You already have a {existing.status} membership ({existing.unique_membership_id}). '
                'Please wait for admin review or contact us to renew.'
            )
            return redirect('membership')
    except UserMembership.DoesNotExist:
        existing = None

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'Offline')
        transaction_id = request.POST.get('transaction_id', '').strip()

        # Validate bKash requires transaction ID
        if payment_method == 'bKash' and not transaction_id:
            messages.error(request, 'Transaction ID is required for bKash payments.')
            return redirect('apply_membership', plan_id=plan_id)

        if existing:
            # Renewal — update existing membership
            existing.plan = plan
            existing.payment_method = payment_method
            existing.transaction_id = transaction_id
            existing.status = UserMembership.STATUS_PENDING
            existing.activated_at = None
            existing.expires_at = None
            existing.save()
            membership = existing
        else:
            # New membership
            membership = UserMembership.objects.create(
                user=user,
                plan=plan,
                payment_method=payment_method,
                transaction_id=transaction_id,
                status=UserMembership.STATUS_PENDING,
            )

        messages.success(
            request,
            f'Your membership application (ID: {membership.unique_membership_id}) has been submitted! '
            'Our team will verify your payment and activate it within 24 hours.'
        )
        return redirect('dashboard')

    context = {
        'plan': plan,
        'page_title': f'Apply for {plan.name}',
    }
    return render(request, 'accounts/apply_membership.html', context)
