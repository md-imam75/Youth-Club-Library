"""
panel/views.py

Custom admin panel views — staff/superuser only.
All views protected by @staff_required decorator.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from django.http import JsonResponse, HttpResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string, get_template
from xhtml2pdf import pisa
from io import BytesIO

from accounts.models import CustomUser, MembershipPlan, UserMembership
from catalog.models import Book, Author, Publication, Category, SocialMediaLink, BookRequest, BookRequestItem, SiteTestimonial
from catalog.forms import BookForm, AuthorForm, PublicationForm, CategoryForm, SocialMediaLinkForm, SiteTestimonialForm
from accounts.forms import MembershipPlanForm
from orders.models import Order, OfflineBill, OfflineBillItem, DeliveryOption
from orders.forms import DeliveryOptionForm


def staff_required(view_func):
    """Decorator: only staff (is_staff=True) can access these views."""
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/accounts/login/'
    )(view_func)
    return login_required(decorated)


# ──────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_dashboard(request):
    """Overview: stats cards + recent activity."""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # --- Stats ---
    total_books = Book.objects.count()
    total_users = CustomUser.objects.filter(is_staff=False).count()

    # Orders
    all_orders = Order.objects.select_related('user', 'book')
    total_buy_orders = all_orders.filter(order_type='Buy').count()
    total_borrow_orders = all_orders.filter(order_type='Borrow').count()
    pending_orders = all_orders.filter(payment_status='Pending').count()

    # Revenue
    total_revenue = all_orders.filter(
        order_type='Buy', payment_status='Paid'
    ).aggregate(total=Sum('total_cost'))['total'] or 0

    month_revenue = all_orders.filter(
        order_type='Buy',
        payment_status='Paid',
        created_at__date__gte=month_start,
    ).aggregate(total=Sum('total_cost'))['total'] or 0

    # Memberships
    pending_memberships = UserMembership.objects.filter(status='Pending').count()
    active_memberships = UserMembership.objects.filter(status='Active').count()

    # Overdue borrows
    overdue_borrows = Order.objects.filter(
        order_type='Borrow',
        due_date__lt=today,
        returned_at__isnull=True,
    ).count()

    # Recent orders (last 10)
    recent_orders = all_orders.order_by('-created_at')[:10]

    # Recent membership requests (last 5 pending)
    recent_memberships = UserMembership.objects.filter(
        status='Pending'
    ).select_related('user', 'plan').order_by('-created_at')[:5]

    context = {
        'page_title': 'Admin Dashboard',
        'total_books': total_books,
        'total_users': total_users,
        'total_buy_orders': total_buy_orders,
        'total_borrow_orders': total_borrow_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'month_revenue': month_revenue,
        'pending_memberships': pending_memberships,
        'active_memberships': active_memberships,
        'overdue_borrows': overdue_borrows,
        'recent_orders': recent_orders,
        'recent_memberships': recent_memberships,
    }
    return render(request, 'admin_panel/dashboard.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# MEMBERSHIP REQUESTS
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_memberships(request):
    """List all membership applications. Approve / decline via POST."""
    status_filter = request.GET.get('status', '')
    qs = UserMembership.objects.select_related('user', 'plan').order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Membership Requests',
        'memberships': page_obj,
        'status_filter': status_filter,
        'pending_count':  UserMembership.objects.filter(status='Pending').count(),
        'active_count':   UserMembership.objects.filter(status='Active').count(),
        'expired_count':  UserMembership.objects.filter(status='Expired').count(),
    }
    return render(request, 'admin_panel/memberships.html', context)


@staff_required
def admin_membership_action(request, pk):
    """Approve or decline a membership request."""
    membership = get_object_or_404(UserMembership, pk=pk)
    action = request.POST.get('action')

    if action == 'approve':
        membership.activate()
        messages.success(
            request,
            f'Membership {membership.unique_membership_id} approved for '
            f'{membership.user.get_full_name()}. '
            f'Expires: {membership.expires_at.strftime("%d %b %Y") if membership.expires_at else "N/A"}'
        )
    elif action == 'decline':
        membership.status = UserMembership.STATUS_EXPIRED
        membership.save()
        messages.warning(
            request,
            f'Membership {membership.unique_membership_id} declined.'
        )
    else:
        messages.error(request, 'Unknown action.')

    return redirect('admin_memberships')


# ──────────────────────────────────────────────────────────────────────────────
# ORDERS
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_orders(request):
    """All orders — filter by type / payment status. Mark paid/returned."""
    order_type = request.GET.get('type', '')
    pay_status = request.GET.get('status', '')
    q = request.GET.get('q', '')

    qs = Order.objects.select_related('user', 'book').order_by('-created_at')
    if order_type:
        qs = qs.filter(order_type=order_type)
    if pay_status:
        qs = qs.filter(payment_status=pay_status)
    if q:
        qs = qs.filter(
            Q(book__title__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Borrow Requests' if order_type == 'Borrow' else 'All Orders',
        'orders': page_obj,
        'order_type': order_type,
        'pay_status': pay_status,
        'q': q,
        'buy_count':     Order.objects.filter(order_type='Buy').count(),
        'borrow_count':  Order.objects.filter(order_type='Borrow').count(),
        'pending_count': Order.objects.filter(payment_status='Pending').count(),
        'paid_count':    Order.objects.filter(payment_status='Paid').count(),
        'total_revenue': Order.objects.filter(order_type='Buy', payment_status='Paid').aggregate(
            t=Sum('total_cost'))['t'] or 0,
    }
    return render(request, 'admin_panel/orders.html', context)


@staff_required
def admin_order_action(request, pk):
    """Mark order paid / failed / returned / delivered / cancelled."""
    order = get_object_or_404(Order, pk=pk)
    group_orders = Order.objects.filter(group_number=order.group_number) if order.group_number else [order]
    action = request.POST.get('action')

    if action == 'mark_paid':
        for o in group_orders:
            o.payment_status = Order.PAYMENT_STATUS_PAID
            o.save()
        messages.success(request, f'Order {order.order_number} marked as Paid.')
        
        # If it is a purchase order, trigger invoice email to the customer
        if order.order_type == Order.ORDER_TYPE_BUY:
            import threading
            threading.Thread(target=send_order_invoice_email_thread, args=(order.pk,)).start()
    elif action == 'mark_failed':
        for o in group_orders:
            o.payment_status = Order.PAYMENT_STATUS_FAILED
            o.save()
        messages.warning(request, f'Order {order.order_number} marked as Failed.')
    elif action == 'mark_returned':
        if order.order_type == 'Borrow' and not order.returned_at:
            order.mark_returned()
            messages.success(request, f'Order #{order.id} marked as returned. Stock restored.')
        else:
            messages.error(request, 'Cannot mark as returned.')
    elif action == 'mark_delivered':
        for o in group_orders:
            o.order_status = Order.STATUS_DELIVERED
            o.save()
        messages.success(request, f'Order {order.order_number} marked as Delivered.')
    elif action == 'mark_cancelled':
        for o in group_orders:
            if o.order_status == Order.STATUS_CANCELLED:
                continue
            o.order_status = Order.STATUS_CANCELLED
            # Restore stock if not already restored via return
            if not (o.order_type == Order.ORDER_TYPE_BORROW and o.returned_at):
                o.book.stock_quantity += o.quantity
                o.book.save(update_fields=['stock_quantity'])
            o.save()
        messages.warning(request, f'Order {order.order_number} marked as Cancelled. Stock restored.')
    else:
        messages.error(request, 'Unknown action.')

    return redirect('admin_orders')


# ──────────────────────────────────────────────────────────────────────────────
# BOOKS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_books(request):
    """Books list with search and filters."""
    q = request.GET.get('q', '')
    qs = Book.objects.select_related('author', 'publication', 'category').order_by('-created_at')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__name__icontains=q))

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Manage Books',
        'books': page_obj,
        'q': q,
        'total_books': Book.objects.count(),
        'in_stock': Book.objects.filter(stock_quantity__gt=0).count(),
        'out_of_stock': Book.objects.filter(stock_quantity=0).count(),
        'featured': Book.objects.filter(is_featured=True).count(),
    }
    return render(request, 'admin_panel/books.html', context)


@staff_required
def admin_book_add(request):
    """Add a new book."""
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save()
            messages.success(request, f'Book "{book.title}" added successfully.')
            return redirect('admin_books')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = BookForm()

    context = {'page_title': 'Add Book', 'form': form, 'action': 'Add'}
    return render(request, 'admin_panel/book_form.html', context)


@staff_required
def admin_book_edit(request, pk):
    """Edit an existing book."""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f'Book "{book.title}" updated successfully.')
            return redirect('admin_books')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = BookForm(instance=book)

    context = {'page_title': f'Edit: {book.title}', 'form': form, 'action': 'Save Changes', 'book': book}
    return render(request, 'admin_panel/book_form.html', context)


@staff_required
def admin_book_delete(request, pk):
    """Delete a book."""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Book "{title}" deleted.')
        return redirect('admin_books')

    context = {'page_title': f'Delete: {book.title}', 'book': book}
    return render(request, 'admin_panel/book_confirm_delete.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# MEMBERSHIP PLANS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_plans(request):
    """List all membership plans."""
    plans = MembershipPlan.objects.all()
    context = {
        'page_title': 'Membership Plans',
        'plans': plans,
        'active_count': plans.filter(is_active=True).count(),
    }
    return render(request, 'admin_panel/plans.html', context)


@staff_required
def admin_plan_add(request):
    """Add a new membership plan."""
    if request.method == 'POST':
        form = MembershipPlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f'Plan "{plan.name}" created.')
            return redirect('admin_plans')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = MembershipPlanForm()

    context = {'page_title': 'Add Membership Plan', 'form': form, 'action': 'Create Plan'}
    return render(request, 'admin_panel/plan_form.html', context)


@staff_required
def admin_plan_edit(request, pk):
    """Edit a membership plan."""
    plan = get_object_or_404(MembershipPlan, pk=pk)
    if request.method == 'POST':
        form = MembershipPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, f'Plan "{plan.name}" updated.')
            return redirect('admin_plans')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = MembershipPlanForm(instance=plan)

    context = {'page_title': f'Edit: {plan.name}', 'form': form, 'action': 'Save Changes', 'plan': plan}
    return render(request, 'admin_panel/plan_form.html', context)


@staff_required
def admin_plan_delete(request, pk):
    """Delete a membership plan."""
    plan = get_object_or_404(MembershipPlan, pk=pk)
    if request.method == 'POST':
        name = plan.name
        plan.delete()
        messages.success(request, f'Plan "{name}" deleted.')
        return redirect('admin_plans')

    context = {'page_title': f'Delete: {plan.name}', 'plan': plan}
    return render(request, 'admin_panel/plan_confirm_delete.html', context)


@staff_required
def admin_approve_borrow(request, pk):
    """Approve a borrow request and set its days limit (due date)."""
    from datetime import timedelta
    order = get_object_or_404(Order, pk=pk, order_type=Order.ORDER_TYPE_BORROW)
    if order.order_status != Order.STATUS_PENDING:
        messages.warning(request, "This order is already processed.")
        return redirect('admin_orders')

    if request.method == 'POST':
        try:
            days_limit = int(request.POST.get('days_limit', 14))
        except (ValueError, TypeError):
            days_limit = 14

        order.due_date = timezone.now().date() + timedelta(days=days_limit)
        order.order_status = Order.STATUS_DELIVERED
        order.payment_status = Order.PAYMENT_STATUS_PAID
        order.save()

        messages.success(
            request,
            f"Borrow request {order.order_number} approved! Due date: {order.due_date.strftime('%d %b %Y')} ({days_limit} days)."
        )
        return redirect('admin_orders')

    context = {
        'order': order,
        'page_title': f'Approve Borrow — {order.order_number}',
    }
    return render(request, 'admin_panel/approve_borrow.html', context)


@staff_required
def admin_users(request):
    """List all registered users for details and borrow stats."""
    from accounts.models import CustomUser
    q = request.GET.get('q', '')
    users = CustomUser.objects.all().order_by('-date_joined')
    if q:
        users = users.filter(
            models.Q(username__icontains=q) |
            models.Q(email__icontains=q) |
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q)
        )

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(users, 20)  # 20 users per page
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'users': page_obj,
        'q': q,
        'page_title': 'User Management',
    }
    return render(request, 'admin_panel/users.html', context)


@staff_required
def admin_user_detail(request, pk):
    """Display user details with borrow statistics."""
    from accounts.models import CustomUser
    user = get_object_or_404(CustomUser, pk=pk)

    borrow_orders = Order.objects.filter(user=user, order_type=Order.ORDER_TYPE_BORROW).order_by('-created_at')
    total_borrows = borrow_orders.count()

    in_time_returns = 0
    late_returns = 0
    active_borrows = []

    for o in borrow_orders:
        if o.returned_at:
            # Check if returned on or before due date
            if o.returned_at.date() <= o.due_date:
                in_time_returns += 1
            else:
                late_returns += 1
        else:
            # Active borrow - check if it is already late
            is_late = timezone.now().date() > o.due_date
            if is_late:
                late_returns += 1  # count as late return because it's past limit and not back yet
            
            delta = o.due_date - timezone.now().date()
            active_borrows.append({
                'order': o,
                'days_remaining': max(0, delta.days),
                'is_overdue': is_late,
                'days_overdue': max(0, -delta.days),
            })

    context = {
        'target_user': user,
        'total_borrows': total_borrows,
        'in_time_returns': in_time_returns,
        'late_returns': late_returns,
        'active_borrows': active_borrows,
        'borrow_orders': borrow_orders,
        'page_title': f'User Profile — {user.get_full_name()}',
    }
    return render(request, 'admin_panel/user_detail.html', context)


@staff_required
def admin_create_ajax(request):
    """AJAX endpoint to dynamically create Author, Publication, or Category."""
    import json
    from django.http import JsonResponse
    from catalog.models import Author, Publication, Category
    from django.utils.text import slugify
    import random

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body)
        model_type = data.get('model_type')
        name = data.get('name', '').strip()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not name:
        return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

    try:
        if model_type == 'author':
            obj, created = Author.objects.get_or_create(name=name)
        elif model_type == 'publication':
            obj, created = Publication.objects.get_or_create(name=name)
        elif model_type == 'category':
            slug = slugify(name)
            if not slug:
                slug = f"cat-{random.randint(10000, 99999)}"
            base_slug = slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            obj, created = Category.objects.get_or_create(name=name, defaults={'slug': slug})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid model type'}, status=400)

        return JsonResponse({
            'success': True,
            'id': obj.id,
            'name': obj.name,
            'created': created
        })
    except Exception as e:
        logger.error('admin_create_ajax error: %s', e, exc_info=True)
        return JsonResponse({'success': False, 'error': 'An internal error occurred. Please try again.'}, status=500)


# ──────────────────────────────────────────────────────────────────────────────
# AUTHORS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_authors(request):
    """List all authors with book counts."""
    q = request.GET.get('q', '')
    qs = Author.objects.annotate(num_books=Count('books')).order_by('-created_at')
    if q:
        qs = qs.filter(name__icontains=q)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Manage Authors',
        'authors': page_obj,
        'q': q,
    }
    return render(request, 'admin_panel/authors.html', context)


@staff_required
def admin_author_add(request):
    """Add a new author."""
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES)
        if form.is_valid():
            author = form.save()
            messages.success(request, f'Author "{author.name}" added successfully.')
            return redirect('admin_authors')
    else:
        form = AuthorForm()

    context = {
        'form': form,
        'page_title': 'Add Author',
        'action': 'Add Author',
    }
    return render(request, 'admin_panel/author_form.html', context)


@staff_required
def admin_author_edit(request, pk):
    """Edit an existing author."""
    author = get_object_or_404(Author, pk=pk)
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES, instance=author)
        if form.is_valid():
            author = form.save()
            messages.success(request, f'Author "{author.name}" updated successfully.')
            return redirect('admin_authors')
    else:
        form = AuthorForm(instance=author)

    context = {
        'form': form,
        'author': author,
        'page_title': f'Edit Author: {author.name}',
        'action': 'Update Author',
    }
    return render(request, 'admin_panel/author_form.html', context)


@staff_required
def admin_author_delete(request, pk):
    """Delete an author."""
    author = get_object_or_404(Author, pk=pk)
    if request.method == 'POST':
        name = author.name
        author.delete()
        messages.warning(request, f'Author "{name}" deleted successfully.')
        return redirect('admin_authors')
    context = {
        'item': author,
        'cancel_url': 'admin_authors',
        'page_title': f'Delete Author: {author.name}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLICATIONS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_publications(request):
    """List all publications with book counts."""
    q = request.GET.get('q', '')
    qs = Publication.objects.annotate(num_books=Count('books')).order_by('-created_at')
    if q:
        qs = qs.filter(name__icontains=q)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Manage Publications',
        'publications': page_obj,
        'q': q,
    }
    return render(request, 'admin_panel/publications.html', context)


@staff_required
def admin_publication_add(request):
    """Add a new publication."""
    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES)
        if form.is_valid():
            pub = form.save()
            messages.success(request, f'Publication "{pub.name}" added successfully.')
            return redirect('admin_publications')
    else:
        form = PublicationForm()

    context = {
        'form': form,
        'page_title': 'Add Publication',
        'action': 'Add Publication',
    }
    return render(request, 'admin_panel/publication_form.html', context)


@staff_required
def admin_publication_edit(request, pk):
    """Edit an existing publication."""
    pub = get_object_or_404(Publication, pk=pk)
    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES, instance=pub)
        if form.is_valid():
            pub = form.save()
            messages.success(request, f'Publication "{pub.name}" updated successfully.')
            return redirect('admin_publications')
    else:
        form = PublicationForm(instance=pub)

    context = {
        'form': form,
        'pub': pub,
        'page_title': f'Edit Publication: {pub.name}',
        'action': 'Update Publication',
    }
    return render(request, 'admin_panel/publication_form.html', context)


@staff_required
def admin_publication_delete(request, pk):
    """Delete a publication."""
    pub = get_object_or_404(Publication, pk=pk)
    if request.method == 'POST':
        name = pub.name
        pub.delete()
        messages.warning(request, f'Publication "{name}" deleted successfully.')
        return redirect('admin_publications')
    context = {
        'item': pub,
        'cancel_url': 'admin_publications',
        'page_title': f'Delete Publication: {pub.name}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# CATEGORIES CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_categories(request):
    """List all categories with book counts."""
    q = request.GET.get('q', '')
    qs = Category.objects.annotate(num_books=Count('books')).order_by('name')
    if q:
        qs = qs.filter(name__icontains=q)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Manage Categories',
        'categories': page_obj,
        'q': q,
    }
    return render(request, 'admin_panel/categories.html', context)


@staff_required
def admin_category_add(request):
    """Add a new category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            cat = form.save(commit=False)
            if not cat.slug:
                from django.utils.text import slugify
                import random
                slug = slugify(cat.name)
                if not slug:
                    slug = f"cat-{random.randint(10000, 99999)}"
                base_slug = slug
                counter = 1
                while Category.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                cat.slug = slug
            cat.save()
            messages.success(request, f'Category "{cat.name}" added successfully.')
            return redirect('admin_categories')
    else:
        form = CategoryForm()

    context = {
        'form': form,
        'page_title': 'Add Category',
        'action': 'Add Category',
    }
    return render(request, 'admin_panel/category_form.html', context)


@staff_required
def admin_category_edit(request, pk):
    """Edit an existing category."""
    cat = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=cat)
        if form.is_valid():
            cat = form.save(commit=False)
            if not cat.slug:
                from django.utils.text import slugify
                import random
                slug = slugify(cat.name)
                if not slug:
                    slug = f"cat-{random.randint(10000, 99999)}"
                base_slug = slug
                counter = 1
                while Category.objects.filter(slug=slug).exclude(pk=cat.pk).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                cat.slug = slug
            cat.save()
            messages.success(request, f'Category "{cat.name}" updated successfully.')
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=cat)

    context = {
        'form': form,
        'cat': cat,
        'page_title': f'Edit Category: {cat.name}',
        'action': 'Update Category',
    }
    return render(request, 'admin_panel/category_form.html', context)


@staff_required
def admin_category_delete(request, pk):
    """Delete a category."""
    cat = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = cat.name
        cat.delete()
        messages.warning(request, f'Category "{name}" deleted successfully.')
        return redirect('admin_categories')
    context = {
        'item': cat,
        'cancel_url': 'admin_categories',
        'page_title': f'Delete Category: {cat.name}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# SOCIAL MEDIA LINKS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_social_links(request):
    """List all social media links."""
    links = SocialMediaLink.objects.all().order_by('name')
    context = {
        'page_title': 'Manage Social Media Links',
        'links': links,
    }
    return render(request, 'admin_panel/social_links.html', context)


@staff_required
def admin_social_link_add(request):
    """Add a new social media link."""
    if request.method == 'POST':
        form = SocialMediaLinkForm(request.POST)
        if form.is_valid():
            link = form.save()
            messages.success(request, f'Social media link "{link.name}" added successfully.')
            return redirect('admin_social_links')
    else:
        form = SocialMediaLinkForm()

    context = {
        'form': form,
        'page_title': 'Add Social Media Link',
        'action': 'Add Link',
    }
    return render(request, 'admin_panel/social_link_form.html', context)


@staff_required
def admin_social_link_edit(request, pk):
    """Edit an existing social media link."""
    link = get_object_or_404(SocialMediaLink, pk=pk)
    if request.method == 'POST':
        form = SocialMediaLinkForm(request.POST, instance=link)
        if form.is_valid():
            link = form.save()
            messages.success(request, f'Social media link "{link.name}" updated successfully.')
            return redirect('admin_social_links')
    else:
        form = SocialMediaLinkForm(instance=link)

    context = {
        'form': form,
        'link': link,
        'page_title': f'Edit Social Link: {link.name}',
        'action': 'Update Link',
    }
    return render(request, 'admin_panel/social_link_form.html', context)


@staff_required
def admin_social_link_delete(request, pk):
    """Delete a social media link."""
    link = get_object_or_404(SocialMediaLink, pk=pk)
    if request.method == 'POST':
        name = link.name
        link.delete()
        messages.warning(request, f'Social media link "{name}" deleted successfully.')
        return redirect('admin_social_links')
    context = {
        'item': link,
        'cancel_url': 'admin_social_links',
        'page_title': f'Delete Social Link: {link.name}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# OFFLINE BILLING SYSTEM
# ──────────────────────────────────────────────────────────────────────────────

def render_to_pdf(template_src, context_dict={}):
    """Helper: Render an HTML template into a PDF byte stream."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from django.conf import settings
    import os
    
    # Apply monkey patch to prevent Windows permission issues during PDF generation
    from xhtml2pdf.files import pisaFileObject
    pisaFileObject.getNamedFile = lambda self: self.uri

    try:
        font_regular = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansBengali-Regular.ttf')
        font_bold = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansBengali-Bold.ttf')
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')

        context_dict['font_regular'] = font_regular
        context_dict['font_bold'] = font_bold
        context_dict['logo_path'] = logo_path

        if 'NotoSansBengali' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('NotoSansBengali', font_regular))
        if 'NotoSansBengali-Bold' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('NotoSansBengali-Bold', font_bold))
            
        # Register family so bold tags work automatically
        pdfmetrics.registerFontFamily('NotoSansBengali', normal='NotoSansBengali', bold='NotoSansBengali-Bold')
    except Exception as e:
        logger.error('Font registration error: %s', e)

    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None


def send_bill_email(bill, pdf_data):
    """Helper: Send PDF invoice to client email."""
    if not bill.customer_email:
        return
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    subject = f"Invoice {bill.bill_number} — Youth Club Library"
    html_message = render_to_string('admin_panel/bill_email.html', {'bill': bill})
    plain_message = render_to_string('admin_panel/bill_email.txt', {'bill': bill})

    email = EmailMultiAlternatives(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [bill.customer_email]
    )
    email.attach_alternative(html_message, "text/html")
    email.attach(f"Invoice_{bill.bill_number}.pdf", pdf_data, "application/pdf")
    email.send(fail_silently=False)


def send_order_invoice_email_thread(order_pk):
    """Background thread function to generate and send order invoice PDF."""
    from orders.models import Order
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings

    try:
        order = Order.objects.get(pk=order_pk)
        email_address = order.customer_email or (order.user.email if order.user else None)
        if not email_address:
            return

        # Fetch all orders in the group
        from django.db.models import F, ExpressionWrapper, DecimalField
        if order.group_number:
            group_orders = Order.objects.filter(group_number=order.group_number).select_related('book').annotate(
                item_total=ExpressionWrapper(F('quantity') * F('book_price'), output_field=DecimalField())
            )
        else:
            group_orders = Order.objects.filter(pk=order.pk).select_related('book').annotate(
                item_total=ExpressionWrapper(F('quantity') * F('book_price'), output_field=DecimalField())
            )
        subtotal = sum(o.book_price * o.quantity for o in group_orders)
        delivery_cost = sum(o.delivery_cost for o in group_orders)
        total_cost = subtotal + delivery_cost

        context = {
            'order': order,
            'group_orders': group_orders,
            'subtotal': subtotal,
            'delivery_cost': delivery_cost,
            'total_cost': total_cost,
        }

        # Generate invoice PDF
        pdf_data = render_to_pdf('orders/order_pdf.html', context)
        if not pdf_data:
            return

        subject = f"Invoice for Order {order.order_number} — Youth Club Library"
        html_message = render_to_string('orders/order_email.html', context)
        plain_message = render_to_string('orders/order_email.txt', context)

        email = EmailMultiAlternatives(
            subject,
            plain_message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            [email_address]
        )
        email.attach_alternative(html_message, "text/html")
        email.attach(f"Invoice_{order.order_number}.pdf", pdf_data, "application/pdf")
        email.send()
    except Exception as e:
        logger.error('Failed to send invoice email for order %s: %s', order.order_number if order else 'unknown', e, exc_info=True)


@staff_required
def admin_bill_list(request):
    """List and filter walk-in offline bills."""
    q = request.GET.get('q', '')
    qs = OfflineBill.objects.all().order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(bill_number__icontains=q) |
            Q(customer_name__icontains=q) |
            Q(customer_mobile__icontains=q) |
            Q(customer_email__icontains=q)
        )

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Walk-in Bills',
        'bills': page_obj,
        'q': q,
    }
    return render(request, 'admin_panel/bills.html', context)


@staff_required
def admin_make_bill(request):
    """Create a new offline walk-in customer bill."""
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        customer_mobile = request.POST.get('customer_mobile', '')
        customer_email = request.POST.get('customer_email', '')
        payment_method = request.POST.get('payment_method', 'cash')
        items_json = request.POST.get('items_json', '[]')

        if not customer_name:
            messages.error(request, "Customer name is required.")
            return redirect('admin_make_bill')

        import json
        try:
            items = json.loads(items_json)
        except Exception:
            messages.error(request, "Invalid items structure.")
            return redirect('admin_make_bill')

        if not items:
            messages.error(request, "Please add at least one book to the bill.")
            return redirect('admin_make_bill')

        # Generate unique bill number
        import random
        from django.utils import timezone
        date_str = timezone.now().strftime("%Y%m%d")
        count = OfflineBill.objects.filter(created_at__date=timezone.now().date()).count() + 1
        bill_number = f"BILL-{date_str}-{count:04d}"

        # Create OfflineBill record
        bill = OfflineBill.objects.create(
            bill_number=bill_number,
            customer_name=customer_name,
            customer_mobile=customer_mobile,
            customer_email=customer_email,
            payment_method=payment_method,
            total_amount=0
        )

        total_amount = 0
        for item in items:
            book_id = item.get('id')
            qty = int(item.get('qty', 1))
            book = get_object_or_404(Book, pk=book_id)

            # Reduce inventory
            book.stock_quantity = max(0, book.stock_quantity - qty)
            book.save(update_fields=['stock_quantity'])

            # Pricing snapshot
            regular_price = book.regular_price
            offer_price = book.offer_price

            effective_price = offer_price if offer_price else regular_price
            discount_percent = 0
            if offer_price and regular_price > 0:
                discount_percent = int(((regular_price - offer_price) / regular_price) * 100)

            item_total = effective_price * qty
            total_amount += item_total

            OfflineBillItem.objects.create(
                bill=bill,
                book=book,
                book_title=book.title,
                author_name=book.author.name if book.author else '',
                publication_name=book.publication.name if book.publication else '',
                quantity=qty,
                regular_price=regular_price,
                offer_price=offer_price,
                discount_percent=discount_percent,
                total_price=item_total
            )

            # Create standard Order record to integrate with "All Orders"
            Order.objects.create(
                user=None,
                book=book,
                order_type=Order.ORDER_TYPE_BUY,
                quantity=qty,
                order_status=Order.STATUS_DELIVERED,
                delivery_option='offline_store',
                delivery_cost=0,
                book_price=effective_price,
                total_cost=item_total,
                payment_method=Order.PAYMENT_OFFLINE if payment_method == 'cash' else Order.PAYMENT_BKASH,
                payment_status=Order.PAYMENT_STATUS_PAID,
                customer_name=customer_name,
                customer_mobile=customer_mobile,
                customer_email=customer_email,
                bill_number=bill_number,
                group_number=bill_number,
            )

        bill.total_amount = total_amount
        bill.save(update_fields=['total_amount'])

        # Generate PDF for emailing
        pdf_data = render_to_pdf('admin_panel/bill_pdf.html', {'bill': bill})
        if pdf_data and customer_email:
            send_bill_email(bill, pdf_data)
            messages.success(request, f"Bill #{bill.bill_number} created and emailed to {customer_email}.")
        else:
            messages.success(request, f"Bill #{bill.bill_number} created successfully.")

        return redirect('admin_bill_list')

    context = {
        'page_title': 'Make a Bill',
    }
    return render(request, 'admin_panel/make_bill.html', context)


@staff_required
def admin_bill_download_pdf(request, pk):
    """Generate and stream PDF download for a specific offline bill."""
    bill = get_object_or_404(OfflineBill, pk=pk)
    pdf_data = render_to_pdf('admin_panel/bill_pdf.html', {'bill': bill})
    if pdf_data:
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f"Invoice_{bill.bill_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF invoice", status=500)


@staff_required
def admin_book_search_ajax(request):
    """AJAX: Search books for offline billing invoice adding."""
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse({'books': []})

    books = Book.objects.filter(
        Q(title__icontains=q) |
        Q(author__name__icontains=q) |
        Q(publication__name__icontains=q)
    )[:10]

    results = []
    for b in books:
        effective_price = float(b.offer_price) if b.offer_price else float(b.regular_price)
        discount_percent = 0
        if b.offer_price and b.regular_price > 0:
            discount_percent = int(((b.regular_price - b.offer_price) / b.regular_price) * 100)

        results.append({
            'id': b.id,
            'title': b.title,
            'author': b.author.name if b.author else 'No Author',
            'publication': b.publication.name if b.publication else 'No Publication',
            'regular_price': float(b.regular_price),
            'offer_price': float(b.offer_price) if b.offer_price else None,
            'effective_price': effective_price,
            'discount_percent': discount_percent,
            'stock': b.stock_quantity
        })

    return JsonResponse({'books': results})


# ──────────────────────────────────────────────────────────────────────────────
# BOOK REQUESTS CRUD
# ──────────────────────────────────────────────────────────────────────────────

@staff_required
def admin_book_requests(request):
    """List all custom user requested books."""
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    qs = BookRequest.objects.all().prefetch_related('items').order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(items__book_title__icontains=q)
        ).distinct()

    if status:
        qs = qs.filter(status=status)

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': 'Book Requests',
        'requests': page_obj,
        'q': q,
        'selected_status': status,
        'status_choices': BookRequest.STATUS_CHOICES,
    }
    return render(request, 'admin_panel/requests.html', context)


@staff_required
def admin_book_request_action(request, pk):
    """Change the status of a specific user book request."""
    book_req = get_object_or_404(BookRequest, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('status')
        if action in dict(BookRequest.STATUS_CHOICES):
            book_req.status = action
            book_req.save(update_fields=['status'])
            messages.success(request, f"Request by {book_req.name} updated to {action}.")
        else:
            messages.error(request, "Invalid status choice.")
    return redirect('admin_book_requests')


@staff_required
def admin_book_request_delete(request, pk):
    """Delete a user requested book record."""
    book_req = get_object_or_404(BookRequest, pk=pk)
    if request.method == 'POST':
        name = book_req.name
        book_req.delete()
        messages.warning(request, f"Book request by {name} deleted successfully.")
        return redirect('admin_book_requests')

    context = {
        'item': f"Book request by {book_req.name}",
        'cancel_url': 'admin_book_requests',
        'page_title': f"Delete Book Request by {book_req.name}",
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


@staff_required
def admin_sales_report(request):
    """Generate and view daily, weekly, and monthly reports based on sales."""
    from django.db.models import F, Sum, ExpressionWrapper, DecimalField
    from django.utils import timezone
    from datetime import datetime, timedelta

    report_type = request.GET.get('report_type', 'daily') # daily, weekly, monthly
    selected_date_str = request.GET.get('date', '')
    selected_month_str = request.GET.get('month', '') # YYYY-MM

    today = timezone.now().date()
    start_date = today
    end_date = today

    if report_type == 'daily':
        if selected_date_str:
            try:
                start_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = today
        end_date = start_date
    elif report_type == 'weekly':
        if selected_date_str:
            try:
                start_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = today - timedelta(days=today.weekday())
        else:
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif report_type == 'monthly':
        if selected_month_str:
            try:
                year_str, month_str = selected_month_str.split('-')
                start_date = datetime(int(year_str), int(month_str), 1).date()
            except (ValueError, TypeError, IndexError):
                start_date = today.replace(day=1)
        else:
            start_date = today.replace(day=1)
        
        # Calculate last day of the month
        if start_date.month == 12:
            end_date = datetime(start_date.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(start_date.year, start_date.month + 1, 1).date() - timedelta(days=1)

    # Query matching paid sales
    orders = Order.objects.filter(
        order_type=Order.ORDER_TYPE_BUY,
        payment_status=Order.PAYMENT_STATUS_PAID,
        created_at__date__range=[start_date, end_date]
    ).select_related('book')

    # Compute metrics
    # Revenue = qty * book_price
    # COGS = qty * buying_price
    # Profit = qty * (book_price - buying_price)
    annotated_orders = orders.annotate(
        item_revenue=ExpressionWrapper(F('quantity') * F('book_price'), output_field=DecimalField()),
        item_cogs=ExpressionWrapper(F('quantity') * F('book__buying_price'), output_field=DecimalField()),
        item_profit=ExpressionWrapper(F('quantity') * (F('book_price') - F('book__buying_price')), output_field=DecimalField()),
        unit_profit=ExpressionWrapper(F('book_price') - F('book__buying_price'), output_field=DecimalField())
    )

    aggregates = annotated_orders.aggregate(
        total_items=Sum('quantity'),
        total_revenue=Sum('item_revenue'),
        total_cogs=Sum('item_cogs'),
        total_profit=Sum('item_profit')
    )

    total_orders = orders.count()
    total_items = aggregates['total_items'] or 0
    total_revenue = aggregates['total_revenue'] or 0
    total_cogs = aggregates['total_cogs'] or 0
    total_profit = aggregates['total_profit'] or 0

    context = {
        'page_title': 'Sales & Profit Reports',
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'selected_date_str': start_date.strftime('%Y-%m-%d'),
        'selected_month_str': start_date.strftime('%Y-%m'),
        'orders': annotated_orders.order_by('-created_at'),
        'total_orders': total_orders,
        'total_items': total_items,
        'total_revenue': total_revenue,
        'total_cogs': total_cogs,
        'total_profit': total_profit,
    }
    return render(request, 'admin_panel/sales_report.html', context)


@staff_required
def admin_sales_report_pdf(request):
    """Generate and download PDF of the sales report."""
    from django.db.models import F, Sum, ExpressionWrapper, DecimalField
    from django.utils import timezone
    from datetime import datetime, timedelta

    report_type = request.GET.get('report_type', 'daily')
    selected_date_str = request.GET.get('date', '')
    selected_month_str = request.GET.get('month', '')

    today = timezone.now().date()
    start_date = today
    end_date = today

    if report_type == 'daily':
        if selected_date_str:
            try:
                start_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = today
        end_date = start_date
    elif report_type == 'weekly':
        if selected_date_str:
            try:
                start_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = today - timedelta(days=today.weekday())
        else:
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif report_type == 'monthly':
        if selected_month_str:
            try:
                year_str, month_str = selected_month_str.split('-')
                start_date = datetime(int(year_str), int(month_str), 1).date()
            except (ValueError, TypeError, IndexError):
                start_date = today.replace(day=1)
        else:
            start_date = today.replace(day=1)
        
        if start_date.month == 12:
            end_date = datetime(start_date.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(start_date.year, start_date.month + 1, 1).date() - timedelta(days=1)

    orders = Order.objects.filter(
        order_type=Order.ORDER_TYPE_BUY,
        payment_status=Order.PAYMENT_STATUS_PAID,
        created_at__date__range=[start_date, end_date]
    ).select_related('book')

    annotated_orders = orders.annotate(
        item_revenue=ExpressionWrapper(F('quantity') * F('book_price'), output_field=DecimalField()),
        item_cogs=ExpressionWrapper(F('quantity') * F('book__buying_price'), output_field=DecimalField()),
        item_profit=ExpressionWrapper(F('quantity') * (F('book_price') - F('book__buying_price')), output_field=DecimalField()),
        unit_profit=ExpressionWrapper(F('book_price') - F('book__buying_price'), output_field=DecimalField())
    )

    aggregates = annotated_orders.aggregate(
        total_items=Sum('quantity'),
        total_revenue=Sum('item_revenue'),
        total_cogs=Sum('item_cogs'),
        total_profit=Sum('item_profit')
    )

    total_orders = orders.count()
    total_items = aggregates['total_items'] or 0
    total_revenue = aggregates['total_revenue'] or 0
    total_cogs = aggregates['total_cogs'] or 0
    total_profit = aggregates['total_profit'] or 0

    context = {
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'orders': annotated_orders.order_by('-created_at'),
        'total_orders': total_orders,
        'total_items': total_items,
        'total_revenue': total_revenue,
        'total_cogs': total_cogs,
        'total_profit': total_profit,
        'generated_at': timezone.now(),
    }
    
    pdf_data = render_to_pdf('admin_panel/sales_report_pdf.html', context)
    if pdf_data:
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f"Sales_Report_{report_type}_{start_date.strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error generating report PDF", status=500)


@staff_required
def admin_testimonials(request):
    """List all site testimonials."""
    testimonials = SiteTestimonial.objects.all().order_by('-created_at')
    context = {
        'page_title': 'Manage Testimonials',
        'testimonials': testimonials,
    }
    return render(request, 'admin_panel/testimonials.html', context)


@staff_required
def admin_testimonial_add(request):
    """Add a new site testimonial."""
    if request.method == 'POST':
        form = SiteTestimonialForm(request.POST)
        if form.is_valid():
            testimonial = form.save()
            messages.success(request, f'Testimonial by "{testimonial.name}" added successfully.')
            return redirect('admin_testimonials')
    else:
        form = SiteTestimonialForm()

    context = {
        'form': form,
        'page_title': 'Add Testimonial',
        'action': 'Add Testimonial',
    }
    return render(request, 'admin_panel/testimonial_form.html', context)


@staff_required
def admin_testimonial_edit(request, pk):
    """Edit an existing site testimonial."""
    testimonial = get_object_or_404(SiteTestimonial, pk=pk)
    if request.method == 'POST':
        form = SiteTestimonialForm(request.POST, instance=testimonial)
        if form.is_valid():
            testimonial = form.save()
            messages.success(request, f'Testimonial by "{testimonial.name}" updated successfully.')
            return redirect('admin_testimonials')
    else:
        form = SiteTestimonialForm(instance=testimonial)

    context = {
        'form': form,
        'testimonial': testimonial,
        'page_title': f'Edit Testimonial: {testimonial.name}',
        'action': 'Update Testimonial',
    }
    return render(request, 'admin_panel/testimonial_form.html', context)


@staff_required
def admin_testimonial_delete(request, pk):
    """Delete a site testimonial."""
    testimonial = get_object_or_404(SiteTestimonial, pk=pk)
    if request.method == 'POST':
        name = testimonial.name
        testimonial.delete()
        messages.warning(request, f'Testimonial by "{name}" deleted successfully.')
        return redirect('admin_testimonials')
    context = {
        'item': testimonial,
        'cancel_url': 'admin_testimonials',
        'page_title': f'Delete Testimonial: {testimonial.name}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


@staff_required
def admin_delivery_options(request):
    """List all delivery options."""
    options = DeliveryOption.objects.all().order_by('cost', 'label')
    context = {
        'options': options,
        'page_title': 'Manage Delivery Options',
    }
    return render(request, 'admin_panel/delivery_options.html', context)


@staff_required
def admin_delivery_option_add(request):
    """Add a new delivery option."""
    if request.method == 'POST':
        form = DeliveryOptionForm(request.POST)
        if form.is_valid():
            option = form.save()
            messages.success(request, f'Delivery option "{option.label}" added successfully.')
            return redirect('admin_delivery_options')
    else:
        form = DeliveryOptionForm()

    context = {
        'form': form,
        'page_title': 'Add Delivery Option',
        'action': 'Add Option',
    }
    return render(request, 'admin_panel/delivery_option_form.html', context)


@staff_required
def admin_delivery_option_edit(request, pk):
    """Edit an existing delivery option."""
    option = get_object_or_404(DeliveryOption, pk=pk)
    if request.method == 'POST':
        form = DeliveryOptionForm(request.POST, instance=option)
        if form.is_valid():
            option = form.save()
            messages.success(request, f'Delivery option "{option.label}" updated successfully.')
            return redirect('admin_delivery_options')
    else:
        form = DeliveryOptionForm(instance=option)

    context = {
        'form': form,
        'option': option,
        'page_title': f'Edit Delivery Option: {option.label}',
        'action': 'Update Option',
    }
    return render(request, 'admin_panel/delivery_option_form.html', context)


@staff_required
def admin_delivery_option_delete(request, pk):
    """Delete a delivery option."""
    option = get_object_or_404(DeliveryOption, pk=pk)
    if request.method == 'POST':
        label = option.label
        option.delete()
        messages.warning(request, f'Delivery option "{label}" deleted successfully.')
        return redirect('admin_delivery_options')
    context = {
        'item': option,
        'cancel_url': 'admin_delivery_options',
        'page_title': f'Delete Delivery Option: {option.label}',
    }
    return render(request, 'admin_panel/confirm_delete.html', context)


