def global_nav(request):
    """Makes the navigation menu and active social media links available to all templates."""
    from catalog.models import SocialMediaLink
    nav_menu = [
        {'label': 'Home', 'url_name': 'home'},
        {'label': 'Books', 'url_name': 'books'},
        {'label': 'Authors', 'url_name': 'authors'},
        {'label': 'Publications', 'url_name': 'publications'},
        {'label': 'Membership', 'url_name': 'membership'},
    ]
    # Sum the quantities of all items stored in request.session['cart']
    cart = request.session.get('cart', {})
    cart_count = 0
    if isinstance(cart, dict):
        for val in cart.values():
            try:
                cart_count += int(val)
            except (ValueError, TypeError):
                pass
                
    active_social_links = SocialMediaLink.objects.filter(is_active=True).order_by('name')

    return {
        'nav_menu': nav_menu,
        'cart_count': cart_count,
        'active_social_links': active_social_links,
    }