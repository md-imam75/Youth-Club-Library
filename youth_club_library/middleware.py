"""
Project-level middleware.
"""


class SecurityHeadersMiddleware:
    """
    Adds browser hardening headers that Django's SecurityMiddleware does not cover.

    * Permissions-Policy: deny powerful browser features we don't use. The camera is
      allowed for our own origin only (the admin barcode scanner needs it).
    * X-Permitted-Cross-Domain-Policies: block Flash/PDF cross-domain data loading.
    * Cache-Control: private/no-store on authenticated + admin pages so personal data
      and invoices are never kept in shared/proxy caches or the browser back/forward cache.
    """

    PERMISSIONS_POLICY = (
        'camera=(self), microphone=(), geolocation=(), payment=(), usb=(), '
        'magnetometer=(), gyroscope=(), accelerometer=(), interest-cohort=()'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', self.PERMISSIONS_POLICY)
        response.setdefault('X-Permitted-Cross-Domain-Policies', 'none')

        # Never let shared caches store logged-in or admin responses.
        if request.path.startswith(('/admin-panel/', '/admin/', '/dashboard/', '/orders/')) \
                or (hasattr(request, 'user') and request.user.is_authenticated):
            if 'Cache-Control' not in response:
                response['Cache-Control'] = 'private, no-store'
        return response
