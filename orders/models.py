"""
orders/models.py

Model: Order (book purchases and borrows)
"""

from django.db import models
from django.utils import timezone





class Order(models.Model):
    ORDER_TYPE_BUY = 'Buy'
    ORDER_TYPE_BORROW = 'Borrow'
    ORDER_TYPE_CHOICES = [
        (ORDER_TYPE_BUY, 'Buy'),
        (ORDER_TYPE_BORROW, 'Borrow'),
    ]

    PAYMENT_OFFLINE = 'Offline'
    PAYMENT_BKASH = 'bKash'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_OFFLINE, 'Offline / Cash on Delivery'),
        (PAYMENT_BKASH, 'bKash'),
    ]

    PAYMENT_STATUS_PENDING = 'Pending'
    PAYMENT_STATUS_PAID = 'Paid'
    PAYMENT_STATUS_FAILED = 'Failed'
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, 'Pending'),
        (PAYMENT_STATUS_PAID, 'Paid'),
        (PAYMENT_STATUS_FAILED, 'Failed'),
    ]

    STATUS_PENDING = 'Pending'
    STATUS_DELIVERED = 'Delivered'
    STATUS_CANCELLED = 'Cancelled'
    ORDER_STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]



    # Core relations
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='orders',
        null=True,
        blank=True
    )
    customer_name = models.CharField(max_length=150, blank=True)
    customer_mobile = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    bill_number = models.CharField(max_length=50, blank=True)
    book = models.ForeignKey(
        'catalog.Book',
        on_delete=models.CASCADE,
        related_name='orders'
    )
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default=ORDER_TYPE_BUY)
    quantity = models.PositiveIntegerField(default=1)
    order_status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default=STATUS_PENDING
    )

    # Delivery
    delivery_option = models.CharField(max_length=100)
    delivery_address = models.TextField(blank=True)
    delivery_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Pricing snapshot at time of order
    book_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    group_number = models.CharField(max_length=50, blank=True, db_index=True)

    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True, help_text='Return due date for borrows')
    returned_at = models.DateTimeField(null=True, blank=True)

    # Admin notes
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'

    def __str__(self):
        return f'Order #{self.id} — {self.user.username} [{self.order_type}] {self.book.title}'

    @property
    def order_number(self):
        if self.bill_number:
            return self.bill_number
        if self.group_number:
            return self.group_number
        if not self.created_at:
            return "YCL-TEMP"
        local_created = timezone.localtime(self.created_at)
        date_str = local_created.strftime('%Y%m%d')
        day_orders_count = Order.objects.filter(
            created_at__date=local_created.date(),
            created_at__lt=self.created_at
        ).count()
        serial = day_orders_count + 1
        return f"YCL-{date_str}-{serial:04d}"

    @property
    def group_total_cost(self):
        if not self.group_number:
            return self.total_cost
        from django.db.models import Sum
        return Order.objects.filter(group_number=self.group_number).aggregate(total=Sum('total_cost'))['total'] or 0

    @property
    def delivery_option_label(self):
        opt = DeliveryOption.objects.filter(code=self.delivery_option).first()
        return opt.label if opt else self.delivery_option

    @property
    def days_remaining(self):
        if self.order_type == self.ORDER_TYPE_BORROW and self.due_date and not self.returned_at:
            delta = self.due_date - timezone.now().date()
            return max(0, delta.days)
        return 0

    @property
    def days_overdue(self):
        if self.order_type == self.ORDER_TYPE_BORROW and self.due_date and not self.returned_at:
            delta = timezone.now().date() - self.due_date
            return max(0, delta.days)
        return 0

    @property
    def is_returned(self):
        return self.returned_at is not None

    @property
    def is_overdue(self):
        if self.order_type == self.ORDER_TYPE_BORROW and self.due_date:
            return not self.is_returned and timezone.now().date() > self.due_date
        return False

    def mark_returned(self):
        self.returned_at = timezone.now()
        # Restore stock
        self.book.stock_quantity += self.quantity
        self.book.save(update_fields=['stock_quantity'])
        self.save(update_fields=['returned_at'])


class OfflineBill(models.Model):
    bill_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=150)
    customer_mobile = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    payment_method = models.CharField(max_length=10, choices=[('cash', 'Cash'), ('bkash', 'bKash')], default='cash')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Offline Bill'
        verbose_name_plural = 'Offline Bills'

    def __str__(self):
        return f"Bill {self.bill_number} — {self.customer_name}"


class OfflineBillItem(models.Model):
    bill = models.ForeignKey(OfflineBill, on_delete=models.CASCADE, related_name='items')
    book = models.ForeignKey('catalog.Book', on_delete=models.SET_NULL, null=True)
    book_title = models.CharField(max_length=250)
    author_name = models.CharField(max_length=200, blank=True)
    publication_name = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percent = models.PositiveIntegerField(default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.book_title} x {self.quantity}"


class DeliveryOption(models.Model):
    label = models.CharField(max_length=150, unique=True, help_text="e.g. Free Delivery — Kazir Dewri")
    code = models.SlugField(max_length=100, unique=True, help_text="Unique lowercase identifier (e.g. free_kazir_dewri)")
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Delivery fee (0.00 for free delivery)")
    is_active = models.BooleanField(default=True, help_text="Whether this option is active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cost', 'label']
        verbose_name = 'Delivery Option'
        verbose_name_plural = 'Delivery Options'

    def __str__(self):
        if self.cost == 0:
            return f"{self.label} (Free)"
        return f"{self.label} (৳{self.cost:.0f})"

