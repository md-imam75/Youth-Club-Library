"""
URL configuration for Youth Club Library.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from catalog.sitemaps import sitemaps
from catalog.views import robots_txt_view

urlpatterns = [
    # SEO: Robots & Sitemap
    path('robots.txt', robots_txt_view, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # Django Admin
    path('admin/', admin.site.urls),

    # Allauth (login, signup, social auth, password reset, etc.)
    path('accounts/', include('allauth.urls')),

    # Local apps
    path('', include('catalog.urls')),              # Home, books, book detail
    path('', include('accounts.urls')),             # Dashboard, membership, profile
    path('orders/', include('orders.urls')),        # Checkout, order history

    # Custom staff admin panel
    path('admin-panel/', include('panel.urls')),   # /admin-panel/
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
