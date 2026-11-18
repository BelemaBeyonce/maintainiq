from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from core.services import onboard


class Command(BaseCommand):
    help = "Operator-only tenant onboarding. Never exposes public self-service admin selection."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--slug", required=True)
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        try:
            tenant = onboard(
                options["name"],
                options["slug"],
                options["email"],
                getpass("New administrator password: "),
            )
        except (ValidationError, IntegrityError) as exc:
            raise CommandError(
                "Onboarding failed: check email, password policy and organization slug"
            ) from exc
        self.stdout.write(
            f"Organization created: {tenant.pk}. Sign in with the supplied administrator email."
        )
