"""
catalog/sitemaps.py

Sitemaps for Youth Club Library:
- StaticViewSitemap: Core landing & static pages
- BookSitemap: All non-upcoming catalog books
- CategorySitemap: All book categories
- AuthorSitemap: All authors & scholars
- PublicationSitemap: All publications
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Book, Category, Author, Publication


class StaticViewSitemap(Sitemap):
    """Sitemap for main structural and navigational pages."""
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return [
            'home',
            'about',
            'books',
            'authors',
            'publications',
            'categories',
            'membership',
            'request_book',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'home':
            return 1.0
        elif item in ('books', 'about', 'membership'):
            return 0.9
        return 0.7

    def changefreq(self, item):
        if item in ('home', 'books'):
            return 'daily'
        return 'weekly'


class BookSitemap(Sitemap):
    """Sitemap for individual book detail pages."""
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Book.objects.filter(is_upcoming=False).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    """Sitemap for book category pages."""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.all().order_by('name')


class AuthorSitemap(Sitemap):
    """Sitemap for authors & scholars."""
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Author.objects.all().order_by('name')


class PublicationSitemap(Sitemap):
    """Sitemap for publications."""
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Publication.objects.all().order_by('name')


sitemaps = {
    'static': StaticViewSitemap,
    'books': BookSitemap,
    'categories': CategorySitemap,
    'authors': AuthorSitemap,
    'publications': PublicationSitemap,
}
