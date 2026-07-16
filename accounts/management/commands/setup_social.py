"""
accounts/management/commands/setup_social.py

Run once after migrate to configure the Site object and Google SocialApp:
    python manage.py setup_social

Reads GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from .env (or env vars).
Safe to re-run -- uses get_or_create.
"""

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = (
        'Configure django.contrib.sites and create/update the '
        'Google OAuth SocialApp so social login works out of the box.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            default='127.0.0.1:8000',
            help='Site domain (default: 127.0.0.1:8000)',
        )
        parser.add_argument(
            '--client-id',
            default='',
            help='Google OAuth Client ID (overrides .env)',
        )
        parser.add_argument(
            '--client-secret',
            default='',
            help='Google OAuth Client Secret (overrides .env)',
        )

    def handle(self, *args, **options):
        from django.conf import settings

        domain = options['domain']
        client_id = options['client_id'] or getattr(settings, 'GOOGLE_CLIENT_ID', '')
        client_secret = options['client_secret'] or getattr(settings, 'GOOGLE_CLIENT_SECRET', '')

        # -- 1. Fix the Site record -------------------------------------------
        site, created = Site.objects.get_or_create(id=settings.SITE_ID)
        old_domain = site.domain
        site.domain = domain
        site.name = 'Youth Club Library'
        site.save()

        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Site created: ' + domain))
        elif old_domain != domain:
            self.stdout.write(self.style.SUCCESS(
                '[OK] Site updated: ' + old_domain + ' -> ' + domain
            ))
        else:
            self.stdout.write('     Site already correct: ' + domain)

        # -- 2. Create / update Google SocialApp ------------------------------
        try:
            from allauth.socialaccount.models import SocialApp

            app, created = SocialApp.objects.get_or_create(provider='google')
            app.name = 'Google'
            app.client_id = client_id or 'REPLACE_WITH_YOUR_GOOGLE_CLIENT_ID'
            app.secret = client_secret or 'REPLACE_WITH_YOUR_GOOGLE_CLIENT_SECRET'
            app.save()

            # Attach to the site (ManyToMany)
            app.sites.add(site)

            status = 'created' if created else 'updated'
            self.stdout.write(self.style.SUCCESS('[OK] Google SocialApp ' + status))

            if not client_id:
                self.stdout.write(self.style.WARNING(
                    '\n[WARN] GOOGLE_CLIENT_ID is not set in your .env file.\n'
                    '       Google login button will redirect but OAuth will fail.\n'
                    '       Steps to fix:\n'
                    '         1. Go to https://console.cloud.google.com/\n'
                    '         2. APIs & Services > Credentials > Create OAuth 2.0 Client ID\n'
                    '         3. Application type: Web application\n'
                    '         4. Authorized redirect URI:\n'
                    '            http://' + domain + '/accounts/google/login/callback/\n'
                    '         5. Copy Client ID + Secret into your .env file\n'
                    '         6. Re-run: python manage.py setup_social\n'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    '     Client ID: ' + client_id[:12] + '...'
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR('[ERROR] Could not create SocialApp: ' + str(e)))
            self.stdout.write(
                'Make sure allauth.socialaccount is in INSTALLED_APPS and migrations are applied.'
            )
            return

        # -- 3. Summary -------------------------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('-' * 52))
        self.stdout.write(self.style.SUCCESS('Social account setup complete!'))
        self.stdout.write('   Site:  http://' + domain)
        self.stdout.write('   Admin: http://' + domain + '/admin/')
        self.stdout.write('   Login: http://' + domain + '/accounts/login/')
        self.stdout.write(self.style.SUCCESS('-' * 52))
