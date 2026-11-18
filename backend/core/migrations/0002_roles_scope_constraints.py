from django.db import migrations

ROLES = {
    "admin": "Organization administrator",
    "manager": "Maintenance manager",
    "engineer": "Reliability engineer",
    "technician": "Technician",
    "requester": "Requester / operator",
    "auditor": "Read-only auditor",
}


def roles(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    for code, name in ROLES.items():
        Role.objects.update_or_create(code=code, defaults={"name": name})


# Composite foreign keys prevent bypassing the service's tenant/site checks.
RELATIONS = [
    (
        "core_membershipsite",
        "ms_membership_scope",
        "membership_id, tenant_id",
        "core_membership",
        "id, tenant_id",
    ),
    ("core_membershipsite", "ms_site_scope", "site_id, tenant_id", "core_site", "id, tenant_id"),
    (
        "core_functionallocation",
        "location_site_scope",
        "site_id, tenant_id",
        "core_site",
        "id, tenant_id",
    ),
    (
        "core_functionallocation",
        "location_parent_scope",
        "parent_id, site_id, tenant_id",
        "core_functionallocation",
        "id, site_id, tenant_id",
    ),
    ("core_asset", "asset_site_scope_fk", "site_id, tenant_id", "core_site", "id, tenant_id"),
    (
        "core_asset",
        "asset_category_scope_fk",
        "category_id, tenant_id",
        "core_assetcategory",
        "id, tenant_id",
    ),
    (
        "core_asset",
        "asset_location_scope_fk",
        "functional_location_id, site_id, tenant_id",
        "core_functionallocation",
        "id, site_id, tenant_id",
    ),
    (
        "core_asset",
        "asset_parent_scope_fk",
        "parent_id, site_id, tenant_id",
        "core_asset",
        "id, site_id, tenant_id",
    ),
    ("core_auditevent", "audit_site_scope", "site_id, tenant_id", "core_site", "id, tenant_id"),
    (
        "core_invitationsite",
        "invite_membership_scope",
        "invitation_id, tenant_id",
        "core_invitation",
        "id, tenant_id",
    ),
    (
        "core_invitationsite",
        "invite_site_scope",
        "site_id, tenant_id",
        "core_site",
        "id, tenant_id",
    ),
]
operations = [migrations.RunPython(roles, migrations.RunPython.noop)]
for table, name, columns, target, targetcols in RELATIONS:
    operations.append(
        migrations.RunSQL(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({columns}) REFERENCES {target} ({targetcols}) DEFERRABLE INITIALLY IMMEDIATE",
            f"ALTER TABLE {table} DROP CONSTRAINT {name}",
        )
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = operations
