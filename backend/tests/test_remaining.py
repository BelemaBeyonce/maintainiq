from urllib.parse import parse_qs, urlsplit

from django.core import mail
from django.core.management import call_command
from django.db import connection

from core.models import Asset, AuditEvent, Membership, Tenant, User
from tests.test_auth import csrf_client, csrf_post


def test_password_reset_delivery_single_use_and_session_invalidation(domain):
    client = csrf_client()
    email = domain["users"]["manager"].email
    assert (
        csrf_post(
            client, "/api/auth/login/", {"email": email, "password": "synthetic-test-passphrase"}
        ).status_code
        == 200
    )
    assert csrf_post(client, "/api/auth/password-reset/", {"email": email}).status_code == 202
    assert len(mail.outbox) == 1
    link = mail.outbox[0].body.split(" ")[-1]
    params = parse_qs(urlsplit(link).fragment)
    payload = {
        "uid": params["uid"][0],
        "token": params["token"][0],
        "password": "updated-synthetic-passphrase",
    }
    anonymous = csrf_client()
    assert csrf_post(anonymous, "/api/auth/password-reset/confirm/", payload).status_code == 200
    assert csrf_post(anonymous, "/api/auth/password-reset/confirm/", payload).status_code == 400
    assert client.get("/api/auth/context/").status_code == 403
    assert (
        csrf_post(
            anonymous, "/api/auth/login/", {"email": email, "password": payload["password"]}
        ).status_code
        == 200
    )
    assert AuditEvent.objects.filter(action="account.password_reset").count() == 1


def test_reset_does_not_reveal_unknown_email(domain):
    client = csrf_client()
    unknown = csrf_post(client, "/api/auth/password-reset/", {"email": "absent@example.com"})
    known = csrf_post(
        client, "/api/auth/password-reset/", {"email": domain["users"]["manager"].email}
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.data == known.data
    assert len(mail.outbox) == 1
    assert (
        csrf_post(
            client,
            "/api/auth/password-reset/confirm/",
            {"uid": "bad", "token": "bad", "password": "updated-synthetic-passphrase"},
        ).status_code
        == 400
    )


def test_organization_settings_and_admin_access(client, domain):
    assert client.get("/api/organization/").data["name"] == domain["a"].name
    assert (
        client.patch("/api/organization/", {"name": "Override"}, format="json").status_code == 403
    )
    client.force_login(domain["users"]["admin"])
    result = client.patch(
        "/api/organization/",
        {"name": "Synthetic revised organization", "timezone": "Africa/Lagos", "currency": "NGN"},
        format="json",
    )
    assert result.status_code == 200
    assert (
        client.patch(
            "/api/organization/", {"timezone": "invalid/unknown"}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.patch("/api/organization/", {"is_synthetic": False}, format="json").status_code
        == 400
    )
    assert client.get("/api/organization/", HTTP_X_TENANT_ID=str(domain["b"].pk)).status_code == 404


def test_seed_idempotent_and_private_credentials(db, tmp_path):
    import json

    path = tmp_path / "demo-credentials.json"
    call_command("seed_demo", credentials_file=str(path))
    first = path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(json.loads(first)) == 12
    assert Tenant.objects.filter(is_synthetic=True).count() == 2
    assert Asset.objects.filter(is_synthetic=True).count() == 4
    event_count = AuditEvent.objects.count()
    call_command("seed_demo", credentials_file=str(path))
    assert path.read_text() == first
    assert User.objects.count() == 12
    assert Membership.objects.count() == 12
    assert AuditEvent.objects.count() == event_count


def test_postgresql_migration_state_and_scope_constraints(db):
    call_command("makemigrations", check=True, dry_run=True, verbosity=0)
    call_command("migrate", check=True, verbosity=0)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conname IN ('asset_site_scope_fk','asset_category_scope_fk','asset_location_scope_fk','asset_parent_scope_fk','ms_membership_scope','ms_site_scope','invite_site_scope','audit_site_scope')"
        )
        assert len(cursor.fetchall()) == 8


def test_reference_edit_permissions_audit_and_location_cycles(client, domain):
    site_url = f"/api/sites/{domain['site'].pk}/"
    assert client.patch(site_url, {"name": "Denied"}, format="json").status_code == 403
    client.force_login(domain["users"]["admin"])
    assert (
        client.patch(site_url, {"name": "Synthetic revised site"}, format="json").status_code == 200
    )
    assert AuditEvent.objects.filter(
        object_id=domain["site"].pk, action="reference.updated"
    ).exists()
    assert (
        client.patch(
            f"/api/sites/{domain['foreign'].pk}/", {"name": "Denied"}, format="json"
        ).status_code
        == 404
    )
    location_url = f"/api/locations/{domain['loc'].pk}/"
    assert (
        client.patch(location_url, {"parent_id": str(domain["loc"].pk)}, format="json").status_code
        == 400
    )
    child = client.post(
        "/api/locations/",
        {
            "site_id": str(domain["site"].pk),
            "parent_id": str(domain["loc"].pk),
            "code": "CHILD",
            "name": "Synthetic child location",
        },
        format="json",
    ).data
    assert client.patch(location_url, {"parent_id": child["id"]}, format="json").status_code == 400
    assert (
        client.patch(location_url, {"site_id": str(domain["hidden"].pk)}, format="json").status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/categories/{domain['cat'].pk}/",
            {"name": "Synthetic revised pumps"},
            format="json",
        ).status_code
        == 200
    )
