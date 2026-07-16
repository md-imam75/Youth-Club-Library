def site_settings(request):
    """Inject global settings into all templates."""
    from django.conf import settings
    return {
        'BKASH_NUMBER': getattr(settings, 'BKASH_NUMBER', '01XXXXXXXXX'),
        'SITE_NAME': 'Youth Club Library',
        'SITE_TAGLINE': 'Read. Learn. Grow.',
    }
