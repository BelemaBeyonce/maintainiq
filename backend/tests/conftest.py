import os
from uuid import uuid4

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-deployment-secret-" + uuid4().hex)
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DEVELOPMENT_INVITE_LINKS", "true")

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from core.models import (
    Asset,
    AssetCategory,
    FunctionalLocation,
    Membership,
    MembershipSite,
    Site,
    Tenant,
    User,
)


@pytest.fixture(autouse=True)
def reset_cache():
    cache.clear()


@pytest.fixture
def domain(db):
    a = Tenant.objects.create(
        name="Synthetic Organization A", slug="synthetic-a", is_synthetic=True
    )
    b = Tenant.objects.create(
        name="Synthetic Organization B", slug="synthetic-b", is_synthetic=True
    )
    site = Site.objects.create(tenant=a, name="Synthetic O&G Site", code="OIL-A", is_synthetic=True)
    hidden = Site.objects.create(tenant=a, name="Restricted Site", code="RESTRICTED")
    foreign = Site.objects.create(
        tenant=b, name="Synthetic B Site", code="B-SITE", is_synthetic=True
    )
    cat = AssetCategory.objects.create(tenant=a, name="Centrifugal pumps", code="pump")
    other_cat = AssetCategory.objects.create(tenant=b, name="Compressors", code="compressor")
    loc = FunctionalLocation.objects.create(
        tenant=a, site=site, code="PROCESS", name="Process area"
    )
    foreign_loc = FunctionalLocation.objects.create(
        tenant=b, site=foreign, code="B-AREA", name="B area"
    )
    asset = Asset.objects.create(
        tenant=a,
        site=site,
        category=cat,
        functional_location=loc,
        tag="P-101",
        name="Synthetic feed pump",
        is_synthetic=True,
    )
    hidden_asset = Asset.objects.create(
        tenant=a, site=hidden, category=cat, tag="HIDDEN", name="Restricted asset"
    )
    foreign_asset = Asset.objects.create(
        tenant=b, site=foreign, category=other_cat, tag="B-101", name="Synthetic B compressor"
    )
    users = {}
    for role in ["admin", "manager", "engineer", "technician", "requester", "auditor"]:
        user = User.objects.create_user(
            f"{role}@synthetic.example.com", "synthetic-test-passphrase", first_name=role
        )
        membership = Membership.objects.create(tenant=a, user=user, role_id=role)
        if role != "admin":
            MembershipSite.objects.create(tenant=a, membership=membership, site=site)
        users[role] = user
    other = User.objects.create_user("b@synthetic.example.com", "synthetic-test-passphrase")
    Membership.objects.create(tenant=b, user=other, role_id="admin")
    return dict(
        a=a,
        b=b,
        site=site,
        hidden=hidden,
        foreign=foreign,
        cat=cat,
        other_cat=other_cat,
        loc=loc,
        foreign_loc=foreign_loc,
        asset=asset,
        hidden_asset=hidden_asset,
        foreign_asset=foreign_asset,
        users=users,
        other=other,
    )


@pytest.fixture
def client(domain):
    client = APIClient()
    client.force_login(domain["users"]["manager"])
    client.defaults["HTTP_X_TENANT_ID"] = str(domain["a"].pk)
    return client


@pytest.fixture
def payload(domain):
    return dict(
        site_id=str(domain["site"].pk),
        category_id=str(domain["cat"].pk),
        functional_location_id=str(domain["loc"].pk),
        tag="P-202",
        name="Synthetic injection pump",
        manufacturer="Synthetic Manufacturer",
        serial_number="SYN-202",
        criticality="high",
        status="standby",
    )
