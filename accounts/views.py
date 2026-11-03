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

    # Order history (fetch once and precompute group totals in memory to avoid N+1 queries)
    all_orders = list(Order.objects.filter(user=user).select_related('book', 'book__author').order_by('-created_at'))
    group_totals = {}
    for o in all_orders:
        if o.group_number:
            group_totals[o.group_number] = group_totals.get(o.group_number, 0) + o.total_cost
    for o in all_orders:
        o._group_total_cost = group_totals.get(o.group_number, o.total_cost) if o.group_number else o.total_cost

    bought_orders = [o for o in all_orders if o.order_type == 'Buy']
    borrowed_orders = [o for o in all_orders if o.order_type == 'Borrow']

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

        # Validate bKash / Nagad requires transaction ID
        if payment_method in ('bKash', 'Nagad') and not transaction_id:
            messages.error(request, 'Transaction ID is required for bKash / Nagad payments.')
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

        # Notify admin
        from youth_club_library.notifications import notify_admin_new_membership
        notify_admin_new_membership(membership)

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


@login_required
def delete_account_view(request):
    """
    Allows a user to permanently delete their account and personal data.
    Orders and transaction histories are unlinked/anonymized to preserve accounting integrity.
    Admin accounts cannot be deleted to prevent accidental loss.
    """
    if request.user.is_staff or request.user.is_superuser:
        messages.error(request, 'Admin accounts cannot be deleted to prevent accidental data loss.')
        return redirect('dashboard')

    if request.method == 'POST':
        user = request.user
        from django.contrib.auth import logout
        # Anonymize orders linked to user before deletion if cascading is not desired
        user.delete()  # Deletes CustomUser record, UserMembership (CASCADE), SocialAccounts
        logout(request)
        messages.success(request, 'Your account and personal data have been permanently deleted.')
        return redirect('home')

    return render(request, 'accounts/delete_account_confirm.html', {
        'page_title': 'Delete Account Confirmation'
    })



@login_required
def download_membership_card(request):
    """Download official digital membership card as PDF for active members."""
    user = request.user
    try:
        membership = user.membership
        membership.check_expiry()
    except UserMembership.DoesNotExist:
        membership = None

    if not membership or membership.status != UserMembership.STATUS_ACTIVE:
        messages.error(request, 'A membership card is only available for members with an active membership plan.')
        return redirect('dashboard')

    from panel.views import render_to_pdf
    from django.http import HttpResponse

    context = {
        'user': user,
        'membership': membership,
        'site_name': 'Youth Club Library',
    }

    pdf_data = render_to_pdf('accounts/membership_card_pdf.html', context)
    if pdf_data:
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f"Membership_Card_{membership.unique_membership_id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    messages.error(request, 'Unable to generate your membership card at this time. Please try again.')
    return redirect('dashboard')
