from .translations import get_translations

def site_settings(request):
    """Inject global settings and translations into all templates."""
    from django.conf import settings

    # Check session, then cookie, default to 'bn' (Bangla)
    lang = request.session.get('user_language')
    if not lang:
        lang = request.COOKIES.get('django_language', 'bn')
    if lang not in ('bn', 'en'):
        lang = 'bn'

    t = get_translations(lang)

    return {
        'BKASH_NUMBER': getattr(settings, 'BKASH_NUMBER', '01XXXXXXXXX'),
        'NAGAD_NUMBER': getattr(settings, 'NAGAD_NUMBER', '01XXXXXXXXX'),
        'SITE_NAME': t['site_name'],
        'SITE_TAGLINE': t['site_tagline'],
        'current_lang': lang,
        't': t,
    }

