"""
WSGI config for youth_club_library project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youth_club_library.settings')
application = get_wsgi_application()
