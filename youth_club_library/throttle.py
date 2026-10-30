"""
Tiny cache-based throttle for public, unauthenticated POST forms.

Uses Django's cache (LocMem by default; automatically shared across workers if a
Redis/Memcached CACHES backend is configured later).

Two independent limits are applied:
  * per client IP  -> stops a single noisy client
  * global          -> backstop that cannot be bypassed by spoofing X-Forwarded-For
"""

from django.core.cache import cache


def client_ip(request):
    """Best-effort client IP behind Render's proxy (first X-Forwarded-For hop)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()[:45]
    return request.META.get('REMOTE_ADDR', 'unknown')[:45]


def _hit(key, limit, window):
    """Increment a counter; return True when the limit is exceeded."""
    cache.add(key, 0, timeout=window)
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add() and incr()
        cache.set(key, 1, timeout=window)
        count = 1
    return count > limit


def is_throttled(request, scope, per_ip_limit=5, global_limit=60, window=3600):
    """Return True if this request should be rejected."""
    ip_blocked = _hit(f'throttle:{scope}:ip:{client_ip(request)}', per_ip_limit, window)
    global_blocked = _hit(f'throttle:{scope}:global', global_limit, window)
    return ip_blocked or global_blocked
