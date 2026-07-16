"""
orders/views.py
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from catalog.models import Book
from .models import Order, DeliveryOption
from .forms import CheckoutForm
from django.utils import timezone
from datetime import timedelta


def generate_order_group_number():
    """Generate a unique order group serial number."""
    from orders.models import Order
    from django.utils import timezone
    local_now = timezone.localtime(timezone.now())
    date_str = local_now.strftime('%Y%m%d')
    # Count distinct group numbers created today
    day_groups_count = Order.objects.filter(
        created_at__date=local_now.date()
    ).values('group_number').distinct().count()
    serial = day_groups_count + 1
    return f"YCL-{date_str}-{serial:04d}"


@login_required
def checkout_view(request, book_id, order_type='Buy'):
    """
    Checkout for buying or borrowing a book.
    order_type is passed via URL: 'buy' or 'borrow'
    """
    book = get_object_or_404(Book, pk=book_id)
    order_type_display = order_type.capitalize()

    # Borrow guard: require active membership
    if order_type == 'borrow':
        if not request.user.has_active_membership:
            messages.warning(
                request,
                '📚 You need an active membership to borrow books. '
                'Please subscribe to a plan and wait for activation.'
            )
            return redirect('membership')
        if not book.can_borrow:
            messages.error(request, 'This book is not available for borrowing.')
            return redirect('book_detail', pk=book.pk)

    # Stock check
    if not book.is_in_stock:
        messages.error(request, 'Sorry, this book is currently out of stock.')
        return redirect('book_detail', pk=book.pk)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            delivery_key = form.cleaned_data['delivery_option']
            opt = DeliveryOption.objects.filter(code=delivery_key, is_active=True).first()
            delivery_cost = float(opt.cost) if opt else 0.0
            book_price = float(book.effective_price)

            if order_type == 'borrow':
                # Borrows are free (membership covers it)
                total_cost = 0
            else:
                total_cost = book_price + delivery_cost

            group_num = generate_order_group_number()
            order = Order.objects.create(
                user=request.user,
                book=book,
                order_type=order_type_display,
                delivery_option=delivery_key,
                delivery_address=form.cleaned_data['delivery_address'],
                delivery_cost=delivery_cost,
                book_price=book_price,
                total_cost=total_cost,
                payment_method=form.cleaned_data['payment_method'],
                transaction_id=form.cleaned_data.get('transaction_id', ''),
                payment_status='Pending',
                due_date=(timezone.now() + timedelta(days=14)).date() if order_type == 'borrow' else None,
                group_number=group_num,
            )

            # Decrease stock
            book.stock_quantity = max(0, book.stock_quantity - 1)
            book.save(update_fields=['stock_quantity'])

            messages.success(
                request,
                f'✅ Your {order_type} order ({order.order_number}) has been placed! '
                'Our team will verify and process it shortly.'
            )
            return redirect('order_success', order_id=order.id)
    else:
        # Pre-fill with user data
        form = CheckoutForm(initial={
            'delivery_address': request.user.address,
        })

    # Delivery pricing for JS
    delivery_costs_json = {opt.code: float(opt.cost) for opt in DeliveryOption.objects.filter(is_active=True)}

    context = {
        'book': book,
        'form': form,
        'order_type': order_type,
        'order_type_display': order_type_display,
        'book_price': float(book.effective_price),
        'delivery_costs_json': delivery_costs_json,
        'delivery_options': DeliveryOption.objects.filter(is_active=True),
        'page_title': f'Checkout — {book.title}',
    }
    return render(request, 'orders/checkout.html', context)


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, 'orders/order_success.html', {
        'order': order,
        'page_title': f'Order {order.order_number} Confirmed',
    })


@login_required
def add_to_cart(request, book_id):
    """Add a book to the session cart."""
    book = get_object_or_404(Book, pk=book_id)
    if book.stock_quantity <= 0:
        messages.error(request, f'Sorry, "{book.title}" is currently out of stock.')
        return redirect('book_detail', pk=book_id)

    cart = request.session.get('cart', {})
    current_qty = cart.get(str(book_id), 0)

    if current_qty >= book.stock_quantity:
        messages.error(request, f'Cannot add more copies of "{book.title}". Only {book.stock_quantity} copies in stock.')
    else:
        cart[str(book_id)] = current_qty + 1
        request.session['cart'] = cart
        messages.success(request, f'"{book.title}" has been added to your cart.')

    return redirect('book_detail', pk=book_id)


@login_required
def cart_view(request):
    """Display items in the user's cart."""
    cart = request.session.get('cart', {})
    cart_items = []
    grand_total = 0

    for book_id, quantity in list(cart.items()):
        try:
            book = Book.objects.get(pk=int(book_id))
            if book.stock_quantity <= 0:
                del cart[book_id]
                continue
            if quantity > book.stock_quantity:
                quantity = book.stock_quantity
                cart[book_id] = quantity

            subtotal = float(book.effective_price) * quantity
            grand_total += subtotal
            cart_items.append({
                'book': book,
                'quantity': quantity,
                'subtotal': subtotal,
            })
        except Book.DoesNotExist:
            del cart[book_id]

    request.session['cart'] = cart

    context = {
        'cart_items': cart_items,
        'grand_total': grand_total,
        'page_title': 'My Shopping Cart',
    }
    return render(request, 'orders/cart.html', context)


@login_required
def update_cart(request, book_id):
    """Update item quantity in the cart."""
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=book_id)
        try:
            qty = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            qty = 1

        cart = request.session.get('cart', {})
        if qty <= 0:
            if str(book_id) in cart:
                del cart[str(book_id)]
        else:
            if qty > book.stock_quantity:
                qty = book.stock_quantity
                messages.warning(request, f'Quantity capped at {book.stock_quantity} (max stock for "{book.title}").')
            cart[str(book_id)] = qty

        request.session['cart'] = cart
    return redirect('cart')


@login_required
def remove_from_cart(request, book_id):
    """Remove item from the cart."""
    cart = request.session.get('cart', {})
    if str(book_id) in cart:
        del cart[str(book_id)]
        request.session['cart'] = cart
        messages.success(request, 'Item removed from cart.')
    return redirect('cart')


@login_required
def cart_checkout_view(request):
    """Checkout all items in the shopping cart."""
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('books')

    cart_items = []
    items_total = 0
    for book_id, quantity in list(cart.items()):
        try:
            book = Book.objects.get(pk=int(book_id))
            if book.stock_quantity <= 0:
                messages.warning(request, f'"{book.title}" is out of stock and was removed.')
                del cart[book_id]
                continue
            if quantity > book.stock_quantity:
                quantity = book.stock_quantity
                cart[book_id] = quantity
            
            subtotal = float(book.effective_price) * quantity
            items_total += subtotal
            cart_items.append({
                'book': book,
                'quantity': quantity,
                'subtotal': subtotal,
            })
        except Book.DoesNotExist:
            del cart[book_id]
    
    request.session['cart'] = cart
    if not cart_items:
        return redirect('cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            delivery_key = form.cleaned_data['delivery_option']
            opt = DeliveryOption.objects.filter(code=delivery_key, is_active=True).first()
            delivery_cost = float(opt.cost) if opt else 0.0
            payment_method = form.cleaned_data['payment_method']
            transaction_id = form.cleaned_data.get('transaction_id', '')
            delivery_address = form.cleaned_data['delivery_address']

            # Double check stock
            for item in cart_items:
                b = Book.objects.get(pk=item['book'].pk)
                if b.stock_quantity < item['quantity']:
                    messages.error(request, f'Sorry, "{b.title}" just went out of stock or doesn\'t have enough copies.')
                    return redirect('cart')

            # Create orders - delivery cost is charged once for the whole cart
            first = True
            created_orders = []
            group_num = generate_order_group_number()
            for item in cart_items:
                b = Book.objects.get(pk=item['book'].pk)
                book_price = float(b.effective_price)
                item_delivery = delivery_cost if first else 0
                item_total = (book_price * item['quantity']) + item_delivery
                
                order = Order.objects.create(
                    user=request.user,
                    book=b,
                    quantity=item['quantity'],
                    order_type=Order.ORDER_TYPE_BUY,
                    delivery_option=delivery_key,
                    delivery_address=delivery_address,
                    delivery_cost=item_delivery,
                    book_price=book_price,
                    total_cost=item_total,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    payment_status='Pending',
                    group_number=group_num,
                )
                created_orders.append(order)

                # Decrease stock
                b.stock_quantity = max(0, b.stock_quantity - item['quantity'])
                b.save(update_fields=['stock_quantity'])
                first = False

            # Clear cart
            request.session['cart'] = {}

            messages.success(request, '✅ Your order has been placed successfully!')
            return redirect('order_success', order_id=created_orders[0].id)
    else:
        form = CheckoutForm(initial={
            'delivery_address': request.user.address,
        })

    delivery_costs_json = {opt.code: float(opt.cost) for opt in DeliveryOption.objects.filter(is_active=True)}

    context = {
        'cart_items': cart_items,
        'items_total': items_total,
        'form': form,
        'delivery_costs_json': delivery_costs_json,
        'delivery_options': DeliveryOption.objects.filter(is_active=True),
        'page_title': 'Checkout',
    }
    return render(request, 'orders/cart_checkout.html', context)


@login_required
def borrow_book_view(request, book_id):
    """
    1-click borrow request for logged-in members.
    Bypasses checkout forms completely.
    """
    book = get_object_or_404(Book, pk=book_id)
    
    # Check membership
    if not request.user.has_active_membership:
        messages.warning(
            request,
            '📚 You need an active membership to borrow books. '
            'Please subscribe to a plan and wait for activation.'
        )
        return redirect('membership')
        
    # Check borrow flag
    if not book.can_borrow:
        messages.error(request, 'This book is not available for borrowing.')
        return redirect('book_detail', pk=book.pk)
        
    # Check stock
    if not book.is_in_stock:
        messages.error(request, 'Sorry, this book is currently out of stock.')
        return redirect('book_detail', pk=book.pk)

    # Create pending borrow order
    group_num = generate_order_group_number()
    order = Order.objects.create(
        user=request.user,
        book=book,
        quantity=1,
        order_type=Order.ORDER_TYPE_BORROW,
        delivery_option='offline_store',
        delivery_address='Offline Pickup',
        delivery_cost=0,
        book_price=0,
        total_cost=0,
        payment_method=Order.PAYMENT_OFFLINE,
        payment_status=Order.PAYMENT_STATUS_PENDING,
        order_status=Order.STATUS_PENDING,
        group_number=group_num,
    )
    
    # Decrease stock
    book.stock_quantity = max(0, book.stock_quantity - 1)
    book.save(update_fields=['stock_quantity'])

    messages.success(request, f'Borrow request for "{book.title}" placed successfully.')
    return redirect('borrow_success', order_id=order.id)


@login_required
def borrow_success_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user, order_type=Order.ORDER_TYPE_BORROW)
    return render(request, 'orders/borrow_success.html', {
        'order': order,
        'page_title': 'Borrow Request Submitted',
    })


@login_required
def order_download_invoice(request, pk):
    """Download invoice PDF for a paid online order."""
    from panel.views import render_to_pdf
    order = get_object_or_404(Order, pk=pk)

    # Security check: must be the owner of the order or staff
    if order.user != request.user and not request.user.is_staff:
        return HttpResponse("Unauthorized", status=403)

    if order.payment_status != Order.PAYMENT_STATUS_PAID:
        return HttpResponse("Invoice is only available for paid orders.", status=400)

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
    # Delivery cost is only charged once per checkout (which is on the first order or we sum them)
    delivery_cost = sum(o.delivery_cost for o in group_orders)
    total_cost = subtotal + delivery_cost

    context = {
        'order': order,
        'group_orders': group_orders,
        'subtotal': subtotal,
        'delivery_cost': delivery_cost,
        'total_cost': total_cost,
    }

    pdf_data = render_to_pdf('orders/order_pdf.html', context)
    if pdf_data:
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f"Invoice_{order.order_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Error generating PDF invoice", status=500)
