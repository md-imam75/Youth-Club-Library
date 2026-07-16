"""
catalog/admin.py
"""

from django.contrib import admin
from .models import Author, Publication, Category, Book, BookReview, SiteTestimonial


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['name', 'book_count', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']

    @admin.display(description='# Books')
    def book_count(self, obj):
        return obj.book_count


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ['name', 'book_count', 'website', 'created_at']
    search_fields = ['name']

    @admin.display(description='# Books')
    def book_count(self, obj):
        return obj.book_count


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'publication', 'category',
        'effective_price', 'stock_quantity', 'is_featured',
        'is_new', 'is_upcoming', 'created_at'
    ]
    list_filter = ['is_featured', 'is_new', 'is_upcoming', 'can_borrow', 'category', 'publication']
    search_fields = ['title', 'author__name', 'publication__name', 'isbn']
    list_editable = ['is_featured', 'is_new', 'is_upcoming', 'stock_quantity']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Book Details', {
            'fields': ('title', 'author', 'publication', 'category', 'cover_image',
                       'description', 'isbn', 'pages', 'language', 'edition')
        }),
        ('Pricing (buying_price is internal)', {
            'fields': ('regular_price', 'offer_price', 'buying_price'),
            'classes': ('collapse',),
        }),
        ('Inventory & Flags', {
            'fields': ('stock_quantity', 'can_borrow', 'is_featured', 'is_new', 'is_upcoming')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_fields(self, request, obj=None):
        """Hide buying_price from non-superusers."""
        fields = super().get_fields(request, obj)
        if not request.user.is_superuser:
            fields = [f for f in fields if f != 'buying_price']
        return fields

    @admin.display(description='Sell Price')
    def effective_price(self, obj):
        return f'৳{obj.effective_price}'


@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['book__title', 'user__username']
    readonly_fields = ['created_at']


@admin.register(SiteTestimonial)
class SiteTestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'rating', 'is_active', 'created_at']
    list_filter = ['rating', 'is_active']
    search_fields = ['name', 'role', 'review_text']
    list_editable = ['is_active']
    readonly_fields = ['created_at']
