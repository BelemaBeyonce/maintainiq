import pytest
from django.db import IntegrityError, transaction

from core.models import Asset, AuditEvent, MembershipSite


def test_crud_search_archive_history(client, domain, payload):
    result = client.post("/api/assets/", payload, format="json")
    assert result.status_code == 201, result.data
    asset_id = result.data["id"]
    url = f"/api/assets/{asset_id}/"
    assert client.get(url).data["tag"] == "P-202"
    result = client.patch(url, {"name": "Synthetic revised pump"}, format="json")
    assert result.status_code == 200, result.data
    assert (
        client.get("/api/assets/?search=revised&criticality=high&status=standby").data["count"] == 1
    )
    assert client.get("/api/assets/?search=absent").data["count"] == 0
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(url + "?include_archived=true").data["archived_at"]
    assert (
        client.patch(
            url + "?include_archived=true", {"name": "Overwrite archived"}, format="json"
        ).status_code
        == 404
    )
    assert client.delete(url + "?include_archived=true").status_code == 404
    events = client.get(url + "history/?include_archived=true").data["results"]
    assert [e["action"] for e in events] == ["asset.archived", "asset.updated", "asset.created"]
    assert events[1]["before"]["name"] == "Synthetic injection pump"
    assert Asset.objects.filter(pk=asset_id).exists()
    assert client.get("/api/dashboard/").data["archived_assets"] == 1


@pytest.mark.parametrize(
    "role,can_write",
    [
        ("admin", True),
        ("manager", True),
        ("engineer", False),
        ("technician", False),
        ("requester", False),
        ("auditor", False),
    ],
)
def test_role_matrix(client, domain, payload, role, can_write):
    client.force_login(domain["users"][role])
    assert client.get("/api/assets/").status_code == 200
    assert client.post("/api/assets/", payload, format="json").status_code == (
        201 if can_write else 403
    )
    if not can_write:
        url = f"/api/assets/{domain['asset'].pk}/"
        assert client.patch(url, {"name": "overwrite"}, format="json").status_code == 403
        assert client.delete(url).status_code == 403
    assert client.post(
        "/api/sites/", {"name": "Unauthorized site", "code": "NEW"}, format="json"
    ).status_code == (201 if role == "admin" else 403)


@pytest.mark.parametrize("method", ["get", "patch", "put", "delete"])
def test_cross_tenant_object_denied(client, domain, payload, method):
    url = f"/api/assets/{domain['foreign_asset'].pk}/"
    kwargs = {"data": payload, "format": "json"} if method in {"patch", "put"} else {}
    assert getattr(client, method)(url, **kwargs).status_code == 404
    assert (
        getattr(client, method)(f"/api/assets/{domain['hidden_asset'].pk}/", **kwargs).status_code
        == 404
    )


def test_scope_list_counts_export_and_org_switch(client, domain):
    assert client.get("/api/assets/").data["count"] == 1
    assert client.get("/api/dashboard/").data["total_assets"] == 1
    result = client.get("/api/assets/export/")
    assert result.status_code == 200
    assert (
        b"P-101" in result.content
        and b"B-101" not in result.content
        and b"HIDDEN" not in result.content
    )
    assert client.get("/api/assets/", HTTP_X_TENANT_ID=str(domain["b"].pk)).status_code == 404
    assert client.get("/api/assets/", HTTP_X_TENANT_ID="invalid").status_code == 400
    assert client.get(f"/api/assets/?site={domain['hidden'].pk}").status_code == 400
    assert client.get(f"/api/assets/?site={domain['foreign'].pk}").status_code == 400
    client.force_login(domain["other"])
    assert client.get("/api/assets/", HTTP_X_TENANT_ID=str(domain["b"].pk)).data["count"] == 1
    assert (
        client.get(
            f"/api/assets/{domain['asset'].pk}/", HTTP_X_TENANT_ID=str(domain["b"].pk)
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "field,foreign",
    [
        ("site_id", "foreign"),
        ("site_id", "hidden"),
        ("category_id", "other_cat"),
        ("functional_location_id", "foreign_loc"),
        ("parent_id", "foreign_asset"),
        ("parent_id", "hidden_asset"),
    ],
)
def test_related_id_injection(client, domain, payload, field, foreign):
    payload[field] = str(domain[foreign].pk)
    result = client.post("/api/assets/", payload, format="json")
    assert result.status_code == 400, result.data
    assert not Asset.objects.filter(tag="P-202").exists()


def test_database_composite_scope_constraints(domain):
    with pytest.raises(IntegrityError), transaction.atomic():
        Asset.objects.create(
            tenant=domain["a"],
            site=domain["foreign"],
            category=domain["cat"],
            tag="WRONG",
            name="bad scope",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        MembershipSite.objects.create(
            tenant=domain["b"],
            membership=domain["users"]["manager"].membership_set.get(),
            site=domain["foreign"],
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Asset.objects.create(
            tenant=domain["a"],
            site=domain["site"],
            category=domain["other_cat"],
            tag="WRONG",
            name="bad category",
        )


def test_unique_tenant_tag_and_hierarchy(client, domain, payload):
    payload["tag"] = "p-101"
    assert client.post("/api/assets/", payload, format="json").status_code == 409
    payload["tag"] = "P-202"
    payload["parent_id"] = str(domain["asset"].pk)
    child = client.post("/api/assets/", payload, format="json").data
    parent_url = f"/api/assets/{domain['asset'].pk}/"
    assert client.patch(parent_url, {"parent_id": child["id"]}, format="json").status_code == 400
    assert client.delete(parent_url).status_code == 409
    assert (
        client.patch(parent_url, {"parent_id": str(domain["asset"].pk)}, format="json").status_code
        == 400
    )
    assert client.delete(f"/api/assets/{child['id']}/").status_code == 204
    assert client.delete(parent_url).status_code == 204
    payload["tag"] = "P-303"
    assert client.post("/api/assets/", payload, format="json").status_code == 400


@pytest.mark.parametrize(
    "patch",
    [
        {"tag": ""},
        {"status": "broken"},
        {"criticality": "unknown"},
        {"tenant_id": "outside"},
        {"is_synthetic": False},
        {"name": "x" * 161},
    ],
)
def test_invalid_input(client, payload, patch):
    assert client.post("/api/assets/", {**payload, **patch}, format="json").status_code == 400


@pytest.mark.parametrize(
    "query",
    [
        "category=invalid",
        "status=invalid",
        "criticality=invalid",
        "search=" + "x" * 101,
        "include_archived=yes",
        "page=999",
    ],
)
def test_invalid_filters(client, query):
    assert client.get("/api/assets/?" + query).status_code in {400, 404}


def test_audit_is_scoped_and_append_only(client, domain, payload):
    asset = client.post("/api/assets/", payload, format="json").data
    event = AuditEvent.objects.get(object_id=asset["id"])
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(ValidationError):
        event.action = "tampered"
        event.save()
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).update(action="tampered")
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).delete()
    client.force_login(domain["other"])
    assert (
        client.get(
            f"/api/audit-events/{event.pk}/", HTTP_X_TENANT_ID=str(domain["b"].pk)
        ).status_code
        == 404
    )
    assert client.get("/api/audit-events/", HTTP_X_TENANT_ID=str(domain["b"].pk)).data["count"] == 0
    assert (
        client.get(
            f"/api/assets/{asset['id']}/history/", HTTP_X_TENANT_ID=str(domain["b"].pk)
        ).status_code
        == 404
    )
