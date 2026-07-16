"""
catalog/forms.py — Book add/edit form for the custom admin panel.
"""

from django import forms
from .models import Book, Author, Publication, Category, SocialMediaLink, SiteTestimonial


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 'author', 'publication', 'category',
            'cover_image', 'description', 'isbn', 'pages',
            'language', 'edition',
            'regular_price', 'offer_price', 'buying_price',
            'stock_quantity', 'can_borrow',
            'is_featured', 'is_new', 'is_upcoming',
        ]
        widgets = {
            'title':         forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Book title'}),
            'author':        forms.Select(attrs={'class': 'form-input'}),
            'publication':   forms.Select(attrs={'class': 'form-input'}),
            'category':      forms.Select(attrs={'class': 'form-input'}),
            'description':   forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Short description'}),
            'isbn':          forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ISBN (optional)'}),
            'pages':         forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 320'}),
            'language':      forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Bangla'}),
            'edition':       forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 3rd edition'}),
            'regular_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00', 'step': '0.01'}),
            'offer_price':   forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Leave blank if no discount', 'step': '0.01'}),
            'buying_price':  forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Internal cost (hidden from users)', 'step': '0.01'}),
            'stock_quantity':forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow blank choices for FK fields
        self.fields['author'].empty_label = '— No author —'
        self.fields['publication'].empty_label = '— No publication —'
        self.fields['category'].empty_label = '— No category —'
        self.fields['author'].required = False
        self.fields['publication'].required = False
        self.fields['category'].required = False
        self.fields['offer_price'].required = False
        self.fields['isbn'].required = False


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'description', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Author Name'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Brief description'}),
        }


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ['name', 'description', 'logo', 'website']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Publication Name'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Brief description'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'Website URL (optional)'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'image', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category Name'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Brief description'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Leave blank to generate automatically'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class SocialMediaLinkForm(forms.ModelForm):
    class Meta:
        model = SocialMediaLink
        fields = ['name', 'url', 'icon_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Facebook'}),
            'url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'e.g. https://www.facebook.com/...'}),
            'icon_type': forms.Select(attrs={'class': 'form-input'}),
        }


class SiteTestimonialForm(forms.ModelForm):
    class Meta:
        model = SiteTestimonial
        fields = ['name', 'role', 'rating', 'review_text', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Nafisa Rahman'}),
            'role': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Avid Reader & Educator'}),
            'rating': forms.Select(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')], attrs={'class': 'form-input'}),
            'review_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Write the review content here...'}),
        }

