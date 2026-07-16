
from pathlib import Path
import os

# Try to load from .env file if python-decouple is available
try:
    from decouple import config
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-ycl-dev-key-change-in-production-!@#$%')
    DEBUG = config('DEBUG', default=True, cast=bool)
    GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
    GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
    BKASH_NUMBER = config('BKASH_NUMBER', default='01XXXXXXXXX')
except ImportError:
    SECRET_KEY = 'django-insecure-ycl-dev-key-change-in-production-!@#$%'
    DEBUG = True
    GOOGLE_CLIENT_ID = ''
    GOOGLE_CLIENT_SECRET = ''
    BKASH_NUMBER = '01XXXXXXXXX'

BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Local apps
    'accounts',
    'catalog',
    'orders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'youth_club_library.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'youth_club_library.context_processors.site_settings',
                'catalog.context_processors.global_nav',
            ],
        },
    },
]

WSGI_APPLICATION = 'youth_club_library.wsgi.application'

# Database — SQLite for development, Neon for production
import dj_database_url
DATABASE_URL = config('DATABASE_URL', default=None)

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# (STATICFILES_STORAGE is now defined inside STORAGES below)

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CLOUDINARY_URL = config('CLOUDINARY_URL', default=None)

# In production (DEBUG=False), we MUST use Cloudinary.
if not DEBUG or CLOUDINARY_URL:
    INSTALLED_APPS.append('cloudinary')
    INSTALLED_APPS.append('cloudinary_storage')
    # Modern Django (4.2+) STORAGES configuration
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    # Fallback for local development if no Cloudinary
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    # Parse the CLOUDINARY_URL explicitly because django-cloudinary-storage 
    # sometimes fails to read os.environ on Render.
    import re
    
    # Default to empty dict
    CLOUDINARY_STORAGE = {'SECURE': True}
    
    if CLOUDINARY_URL:
        # Format: cloudinary://API_KEY:API_SECRET@CLOUD_NAME
        match = re.match(r'^cloudinary://([^:]+):([^@]+)@(.+)$', CLOUDINARY_URL)
        if match:
            CLOUDINARY_STORAGE.update({
                'API_KEY': match.group(1),
                'API_SECRET': match.group(2),
                'CLOUD_NAME': match.group(3),
            })

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Django Allauth ───────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

# Allauth account settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'none'   # Change to 'mandatory' for production with email backend
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_SIGNUP_FORM_CLASS = 'accounts.forms.CustomSignupForm'

# Redirect URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# ─── Google OAuth via django-allauth ──────────────────────────────────────────
# Credentials are stored in the DB (SocialApp model).
# Run:  python manage.py setup_social
# to create/update the Site record and SocialApp automatically.
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # Using DB-based SocialApp (setup_social command creates it).
        # If you prefer settings-based config, set APP here:
        # 'APP': {'client_id': GOOGLE_CLIENT_ID, 'secret': GOOGLE_CLIENT_SECRET},
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',   # forces account picker every time
        },
        'FETCH_USERINFO': True,
    }
}

SOCIALACCOUNT_AUTO_SIGNUP = True       # Skip the confirm-signup page for social logins
SOCIALACCOUNT_LOGIN_ON_GET = True      # Allow GET to trigger social login (no extra form)
SOCIALACCOUNT_QUERY_EMAIL = True       # Always fetch email from Google
SOCIALACCOUNT_STORE_TOKENS = True      # Store OAuth tokens for later use

# Use http for local dev (change to https in production)
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'


# Cache (memory cache for development; use Redis/Memcached in production)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ycl-cache',
    }
}

# Messages storage
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'gray',
    messages.INFO: 'blue',
    messages.SUCCESS: 'green',
    messages.WARNING: 'yellow',
    messages.ERROR: 'red',
}

# Email Settings
try:
    from decouple import config
    EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='no-reply@youthclublibrary.com')
except Exception:
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@youthclublibrary.com')

# Fallback to console email backend if credentials are not configured (local dev)
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

