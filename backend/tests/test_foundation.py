from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction

from core.models import FunctionalLocation, Membership, Role
from core.storage import attachment_key


def test_reference_hierarchy_and_scoped_reads(client, domain):
    assert client.get("/api/sites/").data["count"] == 1
    assert client.get("/api/categories/").data["count"] == 1
    assert client.get("/api/locations/").data["count"] == 1
    assert client.get(f"/api/sites/{domain['foreign'].pk}/").status_code == 404
    client.force_login(domain["users"]["admin"])
    site = client.post(
        "/api/sites/", {"code": "NEW-SYN", "name": "Synthetic new site"}, format="json"
    )
    assert site.status_code == 201
    category = client.post(
        "/api/categories/", {"code": "compressor", "name": "Compressors"}, format="json"
    )
    assert category.status_code == 201
    location = client.post(
        "/api/locations/",
        {
            "code": "UNIT-A",
            "name": "Synthetic process unit",
            "site_id": str(domain["site"].pk),
            "parent_id": str(domain["loc"].pk),
        },
        format="json",
    )
    assert location.status_code == 201
    assert (
        client.post(
            "/api/locations/",
            {
                "code": "BAD",
                "name": "wrong scope",
                "site_id": str(domain["site"].pk),
                "parent_id": str(domain["foreign_loc"].pk),
            },
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/sites/", {"code": "NEW-SYN", "name": "Duplicate"}, format="json"
        ).status_code
        == 409
    )


def test_roles_unique_membership_and_foreign_location_constraints(domain):
    assert Role.objects.count() == 6
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(
            tenant=domain["a"], user=domain["users"]["manager"], role_id="admin"
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        FunctionalLocation.objects.create(
            tenant=domain["a"], site=domain["foreign"], code="BAD", name="Wrong scope"
        )


def test_pagination_and_csv_formula_guard(client, domain, payload):
    for i in range(21):
        payload["tag"] = f"P-{i:03d}"
        payload["name"] = "=untrusted spreadsheet formula"
        assert client.post("/api/assets/", payload, format="json").status_code == 201
    first = client.get("/api/assets/").data
    assert first["count"] == 22 and len(first["results"]) == 20 and first["next"]
    assert len(client.get("/api/assets/?page=2").data["results"]) == 2
    assert b"'=untrusted" in client.get("/api/assets/export/").content
    client.force_login(domain["users"]["requester"])
    assert client.get("/api/assets/export/").status_code == 403
    assert client.get(f"/api/assets/{domain['asset'].pk}/history/").status_code == 403


def test_private_storage_namespace():
    tenant, site = uuid4(), uuid4()
    key = attachment_key(tenant, site, "../../manual.pdf")
    assert key.startswith(f"tenants/{tenant}/sites/{site}/") and ".." not in key
    assert key != attachment_key(tenant, site, "manual.pdf")
    with pytest.raises(ValueError):
        attachment_key(tenant, site, "malware.exe")


def test_health_schema_and_safe_error_handling(client):
    assert client.get("/api/health/").status_code == 200
    result = client.get("/api/schema/")
    assert result.status_code == 200
    assert b"MaintainIQ" in result.content
    response = client.post("/api/assets/", b"{", content_type="application/json")
    assert response.status_code == 400
    assert response.data["error"]["request_id"] == response["X-Request-ID"]
