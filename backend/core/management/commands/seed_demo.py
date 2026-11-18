import json
import os
from pathlib import Path
from secrets import token_urlsafe

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    AssetCategory,
    FunctionalLocation,
    Membership,
    MembershipSite,
    Site,
    Tenant,
    User,
)
from core.scope import Scope
from core.services import create_reference, save_asset


class Command(BaseCommand):
    help = "Idempotently create two explicitly synthetic organizations. Generated credentials stay private."

    def add_arguments(self, parser):
        parser.add_argument("--credentials-file", default="/data/demo-credentials.json")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["credentials_file"])
        existing = json.loads(path.read_text()) if path.exists() else {}
        credentials = dict(existing)
        for label in ["a", "b"]:
            tenant, created = Tenant.objects.get_or_create(
                slug=f"synthetic-org-{label}",
                defaults={"name": f"Synthetic Organization {label.upper()}", "is_synthetic": True},
            )
            if not tenant.is_synthetic:
                raise CommandError("Seed refuses to alter a non-synthetic organization")
            site, _ = Site.objects.get_or_create(
                tenant=tenant,
                code="SYN-OG" if label == "a" else "SYN-WORKSHOP",
                defaults={
                    "name": "Synthetic Oil & Gas Site" if label == "a" else "Synthetic Workshop",
                    "is_synthetic": True,
                },
            )
            for role in ["admin", "manager", "engineer", "technician", "requester", "auditor"]:
                email = f"{role}.{label}@synthetic.maintainiq.test"
                user = User.objects.filter(email=email).first()
                if user is None:
                    password = token_urlsafe(24)
                    user = User.objects.create_user(
                        email, password, first_name=f"Synthetic {role.title()} {label.upper()}"
                    )
                    credentials[email] = password
                membership, _ = Membership.objects.get_or_create(
                    tenant=tenant, user=user, defaults={"role_id": role}
                )
                if role != "admin":
                    MembershipSite.objects.get_or_create(
                        tenant=tenant, membership=membership, site=site
                    )
            admin = User.objects.get(email=f"admin.{label}@synthetic.maintainiq.test")
            scope = Scope(Membership.objects.get(tenant=tenant, user=admin))
            location = FunctionalLocation.objects.filter(
                tenant=tenant, site=site, code="ROTATING"
            ).first()
            if location is None:
                location = create_reference(
                    scope,
                    admin,
                    FunctionalLocation,
                    {
                        "site_id": site.pk,
                        "code": "ROTATING",
                        "name": "Synthetic rotating equipment area",
                    },
                )
            for code, name, tag in [
                ("pump", "Centrifugal pumps", "SYN-P-101"),
                ("compressor", "Compressors", "SYN-C-101"),
            ]:
                category = AssetCategory.objects.filter(tenant=tenant, code=code).first()
                if category is None:
                    category = create_reference(
                        scope, admin, AssetCategory, {"code": code, "name": name}
                    )
                if not tenant.asset_set.filter(tag=tag).exists():
                    save_asset(
                        scope,
                        admin,
                        {
                            "site_id": site.pk,
                            "category_id": category.pk,
                            "functional_location_id": location.pk,
                            "tag": tag,
                            "name": f"Synthetic {name[:-1]} {label.upper()}",
                            "manufacturer": "Synthetic Example Manufacturer",
                            "serial_number": f"SYN-{label.upper()}-{tag}",
                            "status": "active",
                            "criticality": "high",
                            "description": "Synthetic demonstration record. Not a field operating result.",
                        },
                    )
        # Never print passwords into application/Compose logs. Operator explicitly reads this file.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(credentials, output, indent=2)
        os.chmod(path, 0o600)
        self.stdout.write(
            f"Synthetic organizations and assets are ready. Initial generated credentials: {path}. Keep this operator-only file private."
        )
