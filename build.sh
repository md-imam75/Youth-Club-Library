#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input

# Setup django-allauth social accounts (prevents 500 error on login)
if [ -n "$RENDER_EXTERNAL_HOSTNAME" ]; then
    python manage.py setup_social --domain "$RENDER_EXTERNAL_HOSTNAME"
else
    python manage.py setup_social
fi

# If using Option B (Render Automated Superuser)
# Ensure DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD are set in Render
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    python manage.py createsuperuser --no-input || true
fi
