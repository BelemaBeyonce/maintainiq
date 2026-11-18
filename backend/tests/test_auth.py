import hashlib
from datetime import timedelta

import pytest
from django.core import mail
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Invitation, Membership, User
from core.scope import Scope
from core.services import invite, onboard


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/auth/csrf/")
    assert response.status_code == 200
    return client


def csrf_post(client, url, data):
    return client.post(url, data, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def test_login_csrf_context_logout(domain):
    client = csrf_client()
    credentials = {
        "email": "MANAGER@synthetic.example.com",
        "password": "synthetic-test-passphrase",
    }
    assert client.post("/api/auth/login/", credentials, format="json").status_code == 403
    result = csrf_post(client, "/api/auth/login/", credentials)
    assert result.status_code == 200, result.data
    assert client.cookies["sessionid"]["httponly"] is True
    context = client.get("/api/auth/context/").data
    assert len(context["organizations"]) == 1
    assert len(context["organizations"][0]["sites"]) == 1
    assert context["organizations"][0]["role"] == "manager"
    assert client.post("/api/auth/logout/", {}, format="json").status_code == 403
    assert csrf_post(client, "/api/auth/logout/", {}).status_code == 204
    assert client.get("/api/assets/", HTTP_X_TENANT_ID=str(domain["a"].pk)).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "manager@synthetic.example.com", "password": "incorrect"},
        {"email": "absent@example.com", "password": "incorrect"},
        {
            "email": "manager@synthetic.example.com",
            "password": "synthetic-test-passphrase",
            "role": "admin",
        },
    ],
)
def test_login_failures(domain, payload):
    client = csrf_client()
    assert csrf_post(client, "/api/auth/login/", payload).status_code in {400, 401}


def test_disabled_user_and_membership(client, domain):
    user = domain["users"]["manager"]
    user.is_active = False
    user.save()
    assert client.get("/api/auth/context/").status_code == 403
    user.is_active = True
    user.save()
    membership = Membership.objects.get(user=user)
    membership.is_active = False
    membership.save()
    client.force_login(user)
    assert client.get("/api/assets/").status_code == 404


def test_invite_accept_single_use_and_role_not_self_selected(client, domain):
    payload = {
        "email": "new-tech@example.com",
        "role": "technician",
        "site_ids": [str(domain["site"].pk)],
    }
    response = client.post("/api/invitations/", payload, format="json")
    assert response.status_code == 201, response.data
    token = response.data["accept_url"].split("token=")[1]
    invitation = Invitation.objects.get(email=payload["email"])
    assert invitation.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in invitation.token_hash
    assert client.post("/api/invitations/", payload, format="json").status_code == 409
    anon = csrf_client()
    assert (
        csrf_post(anon, "/api/auth/invitations/inspect/", {"token": token}).data["role"]
        == "technician"
    )
    body = {
        "token": token,
        "full_name": "Synthetic technician",
        "password": "new-synthetic-passphrase",
    }
    assert (
        csrf_post(anon, "/api/auth/invitations/accept/", {**body, "role": "admin"}).status_code
        == 400
    )
    assert csrf_post(anon, "/api/auth/invitations/accept/", body).status_code == 201
    assert csrf_post(anon, "/api/auth/invitations/accept/", body).status_code == 400
    membership = Membership.objects.get(user__email=payload["email"])
    assert membership.role_id == "technician"
    assert list(membership.site_grants.values_list("site_id", flat=True)) == [domain["site"].pk]
    assert User.objects.get(email=payload["email"]).password.startswith("argon2")
    assert (
        csrf_post(
            anon, "/api/auth/login/", {"email": payload["email"], "password": body["password"]}
        ).status_code
        == 200
    )
    assert anon.get("/api/assets/", HTTP_X_TENANT_ID=str(domain["b"].pk)).status_code == 404


@pytest.mark.parametrize(
    "role,sites",
    [
        ("admin", "own"),
        ("manager", "own"),
        ("technician", "foreign"),
        ("technician", "hidden"),
        ("technician", "empty"),
        ("technician", "duplicate"),
    ],
)
def test_manager_cannot_escalate_or_grant_unauthorized_sites(client, domain, role, sites):
    ids = (
        []
        if sites == "empty"
        else [
            str(
                domain[
                    {"own": "site", "foreign": "foreign", "hidden": "hidden", "duplicate": "site"}[
                        sites
                    ]
                ].pk
            )
        ]
    )
    if sites == "duplicate":
        ids *= 2
    result = client.post(
        "/api/invitations/",
        {"email": "attack@example.com", "role": role, "site_ids": ids},
        format="json",
    )
    assert result.status_code in {400, 403}
    assert not Invitation.objects.filter(email="attack@example.com").exists()


def test_admin_membership_management_cannot_cross_tenant(client, domain):
    client.force_login(domain["users"]["admin"])
    own = Membership.objects.get(user=domain["users"]["technician"])
    other = Membership.objects.get(user=domain["other"])
    payload = {"role": "engineer", "is_active": True, "site_ids": [str(domain["site"].pk)]}
    assert client.patch(f"/api/memberships/{other.pk}/", payload, format="json").status_code == 404
    assert client.patch(f"/api/memberships/{own.pk}/", payload, format="json").status_code == 200
    self_id = Membership.objects.get(user=domain["users"]["admin"]).pk
    assert client.patch(f"/api/memberships/{self_id}/", payload, format="json").status_code == 409
    client.force_login(domain["users"]["technician"])
    assert client.get("/api/memberships/").status_code == 403
    assert (
        client.post(
            "/api/invitations/",
            {"email": "attack@example.com", "role": "admin", "site_ids": []},
            format="json",
        ).status_code
        == 403
    )


def test_expired_invitation_and_existing_account_protection(client, domain):
    scope = Scope(Membership.objects.get(user=domain["users"]["manager"]))
    invitation, link = invite(
        scope, domain["users"]["manager"], "old@example.com", "technician", [domain["site"].pk]
    )
    invitation.expires_at = timezone.now() - timedelta(seconds=1)
    invitation.save()
    anon = csrf_client()
    token = link.split("token=")[1]
    assert csrf_post(anon, "/api/auth/invitations/inspect/", {"token": token}).status_code == 400
    inv, link = invite(
        scope, domain["users"]["manager"], domain["other"].email, "auditor", [domain["site"].pk]
    )
    body = {
        "token": link.split("token=")[1],
        "full_name": "Existing user",
        "password": "wrong-current-password",
    }
    assert csrf_post(anon, "/api/auth/invitations/accept/", body).status_code == 403
    body["password"] = "synthetic-test-passphrase"
    assert csrf_post(anon, "/api/auth/invitations/accept/", body).status_code == 201
    assert Membership.objects.filter(user=domain["other"]).count() == 2


def test_invitation_email_delivery(client, domain):
    with override_settings(DEVELOPMENT_INVITE_LINKS=False):
        result = client.post(
            "/api/invitations/",
            {"email": "mail@example.com", "role": "engineer", "site_ids": [str(domain["site"].pk)]},
            format="json",
        )
    assert result.status_code == 201
    assert "accept_url" not in result.data
    assert len(mail.outbox) == 1 and "#token=" in mail.outbox[0].body


def test_operator_onboarding_not_public(domain):
    tenant = onboard(
        "Synthetic New Org",
        "synthetic-new",
        "fresh-admin@example.com",
        "strong-synthetic-passphrase",
    )
    membership = Membership.objects.get(tenant=tenant)
    assert membership.role_id == "admin"
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError), transaction.atomic():
        onboard("Other", "other", domain["other"].email, "strong-synthetic-passphrase")


def test_auth_throttling(domain):
    client = csrf_client()
    payload = {"email": "absent@example.com", "password": "incorrect"}
    for _ in range(10):
        assert csrf_post(client, "/api/auth/login/", payload).status_code == 401
    assert csrf_post(client, "/api/auth/login/", payload).status_code == 429
