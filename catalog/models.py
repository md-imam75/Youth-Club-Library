"""
catalog/models.py

Models: Author, Publication, Category, Book, BookReview
"""

from django.db import models
from django.utils.text import slugify
from django.db.models import Avg


class Author(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='authors/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Author'
        verbose_name_plural = 'Authors'

    def __str__(self):
        return self.name

    @property
    def book_count(self):
        return self.books.count()


class Publication(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='publications/', blank=True, null=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Publication'
        verbose_name_plural = 'Publications'

    def __str__(self):
        return self.name

    @property
    def book_count(self):
        return self.books.count()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Book(models.Model):
    title = models.CharField(max_length=300)
    author = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books'
    )
    publication = models.ForeignKey(
        Publication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books'
    )
    cover_image = models.ImageField(upload_to='books/covers/', blank=True, null=True)
    description = models.TextField(blank=True)
    isbn = models.CharField(max_length=20, blank=True, unique=True, null=True)
    pages = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, default='Bangla')
    edition = models.CharField(max_length=50, blank=True)

    # Pricing (buying_price is admin-only visible)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Leave blank if no discount'
    )
    buying_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Internal cost — hidden from customers'
    )
    
    # Manual Competitor Pricing
    wafilife_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Manually enter the price of this book on Wafilife (Optional)'
    )
    wafilife_url = models.URLField(
        blank=True,
        help_text='Direct link to this book on Wafilife (Optional)'
    )

    stock_quantity = models.IntegerField(default=0)
    can_borrow = models.BooleanField(default=True, help_text='Allow members to borrow this book')

    # Homepage display flags
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_upcoming = models.BooleanField(default=False, help_text='Coming soon — not yet available')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Book'
        verbose_name_plural = 'Books'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_stock = self.stock_quantity

    def save(self, *args, **kwargs):
        is_restocked = self.pk and getattr(self, '_original_stock', 0) == 0 and self.stock_quantity > 0
        super().save(*args, **kwargs)
        self._original_stock = self.stock_quantity
        
        if is_restocked:
            import threading
            from django.core.mail import send_mail
            from django.conf import settings
            
            def notify_waitlist():
                waitlist = self.waitlist_entries.select_related('user').all()
                if not waitlist.exists():
                    return
                
                recipient_list = [entry.user.email for entry in waitlist if entry.user.email]
                if recipient_list:
                    subject = f"Good News! '{self.title}' is back in stock!"
                    message = f"Hello,\n\nThe book '{self.title}' you were waiting for is now back in stock.\n\nHurry and grab your copy before it runs out again!\n\nBest,\nLibrary Team"
                    try:
                        send_mail(
                            subject,
                            message,
                            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                            recipient_list,
                            fail_silently=True
                        )
                    except Exception:
                        pass
                
                waitlist.delete()
                
            threading.Thread(target=notify_waitlist).start()

    def __str__(self):
        return self.title

    @property
    def effective_price(self):
        """Return offer_price if set, otherwise regular_price."""
        return self.offer_price if self.offer_price else self.regular_price

    @property
    def discount_percent(self):
        if self.offer_price and self.regular_price:
            discount = ((self.regular_price - self.offer_price) / self.regular_price) * 100
            return round(discount)
        return 0

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    @property
    def average_rating(self):
        result = self.reviews.aggregate(avg=Avg('rating'))
        return round(result['avg'] or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()


class BookReview(models.Model):
    RATING_CHOICES = [(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.IntegerField(choices=RATING_CHOICES)
    review_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'book')
        ordering = ['-created_at']
        verbose_name = 'Book Review'
        verbose_name_plural = 'Book Reviews'

    def __str__(self):
        return f'{self.user.username} → {self.book.title} ({self.rating}★)'


class SocialMediaLink(models.Model):
    ICON_CHOICES = [
        ('facebook', 'Facebook'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('linkedin', 'LinkedIn'),
        ('other', 'Other'),
    ]
    name = models.CharField(max_length=100)
    url = models.URLField()
    icon_type = models.CharField(max_length=20, choices=ICON_CHOICES, default='other')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Social Media Link'
        verbose_name_plural = 'Social Media Links'

    def __str__(self):
        return self.name


class BookRequest(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_REVIEWED = 'Reviewed'
    STATUS_COMPLETED = 'Completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='book_requests',
        help_text='User who made the request (if logged in)'
    )
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Book Request'
        verbose_name_plural = 'Book Requests'

    def __str__(self):
        return f"Request by {self.name} on {self.created_at.strftime('%Y-%m-%d')}"


class BookRequestItem(models.Model):
    request = models.ForeignKey(BookRequest, on_delete=models.CASCADE, related_name='items')
    book_title = models.CharField(max_length=250)
    author = models.CharField(max_length=200, blank=True)
    publication = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.book_title} x {self.quantity}"


class WaitlistEntry(models.Model):
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='waitlist_entries'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='waitlist_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'book')
        ordering = ['created_at']
        verbose_name = 'Waitlist Entry'
        verbose_name_plural = 'Waitlist Entries'

    def __str__(self):
        return f"{self.user.email} waiting for {self.book.title}"


class SiteTestimonial(models.Model):
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, help_text="e.g. University Student, Avid Reader")
    rating = models.PositiveIntegerField(default=5, help_text="Rating from 1 to 5")
    review_text = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Site Testimonial'
        verbose_name_plural = 'Site Testimonials'

    def __str__(self):
        return f"Testimonial by {self.name} ({self.rating} stars)"

