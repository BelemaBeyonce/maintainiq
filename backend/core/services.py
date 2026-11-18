import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Asset,
    AssetCategory,
    AuditEvent,
    FunctionalLocation,
    Invitation,
    InvitationSite,
    Membership,
    MembershipSite,
    Site,
    Tenant,
    User,
)
from .scope import Scope, scoped_assets


class Conflict(ValidationError):
    status_code = 409
    default_code = "conflict"


def audit(scope, actor, action, obj, before=None, after=None, site=None):
    return AuditEvent.objects.create(
        tenant=scope.tenant,
        site=site,
        actor=actor,
        action=action,
        entity_type=type(obj).__name__,
        object_id=obj.pk,
        before=before or {},
        after=after or {},
    )


def snapshot(asset):
    fields = [
        "tag",
        "name",
        "site_id",
        "category_id",
        "functional_location_id",
        "parent_id",
        "manufacturer",
        "model",
        "serial_number",
        "status",
        "criticality",
        "description",
        "archived_at",
        "is_synthetic",
    ]
    return {
        name: (str(value) if isinstance(value, UUID) or hasattr(value, "isoformat") else value)
        for name in fields
        for value in [getattr(asset, name)]
    }


def related(model, scope, identifier, site=None):
    filters = {"tenant": scope.tenant, "pk": identifier}
    if site is not None:
        filters["site"] = site
    try:
        return model.objects.get(**filters)
    except model.DoesNotExist:
        raise ValidationError(
            {"relationship": "Related record unavailable in the selected organization/site"}
        ) from None


def locked_active_asset(scope, identifier):
    try:
        return scoped_assets(scope).select_for_update(of=("self",)).get(pk=identifier)
    except Asset.DoesNotExist:
        raise Http404("Asset unavailable") from None


@transaction.atomic
def save_asset(scope, actor, data, asset=None):
    scope.require_roles("admin", "manager")
    Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    if asset:
        asset = locked_active_asset(scope, asset.pk)
    before = snapshot(asset) if asset else {}
    site = scope.site(data.get("site_id", asset.site_id if asset else None))
    if asset and asset.site_id != site.pk:
        raise ValidationError(
            {
                "site_id": "Site transfers require a separate reviewed workflow; site is immutable in M1"
            }
        )
    category = related(
        AssetCategory, scope, data.get("category_id", asset.category_id if asset else None)
    )
    location_id = data.get(
        "functional_location_id", asset.functional_location_id if asset else None
    )
    location = related(FunctionalLocation, scope, location_id, site) if location_id else None
    parent_id = data.get("parent_id", asset.parent_id if asset else None)
    parent = related(Asset, scope, parent_id, site) if parent_id else None
    if parent and parent.archived_at:
        raise ValidationError({"parent_id": "Archived assets cannot be parents"})
    ancestor = parent
    visited = set()
    while ancestor:
        if ancestor.pk in visited or (asset and ancestor.pk == asset.pk):
            raise ValidationError({"parent_id": "Asset hierarchy would contain a cycle"})
        visited.add(ancestor.pk)
        if len(visited) > 100:
            raise ValidationError({"parent_id": "Hierarchy is limited to 100 levels"})
        ancestor = ancestor.parent
    values = {
        key: value
        for key, value in data.items()
        if key not in {"site_id", "category_id", "functional_location_id", "parent_id"}
    }
    created = asset is None
    asset = asset or Asset(tenant=scope.tenant, is_synthetic=scope.tenant.is_synthetic)
    for key, value in values.items():
        setattr(asset, key, value)
    asset.site, asset.category, asset.functional_location, asset.parent = (
        site,
        category,
        location,
        parent,
    )
    asset.full_clean(validate_unique=False, validate_constraints=False)
    asset.save()
    audit(
        scope,
        actor,
        "asset.created" if created else "asset.updated",
        asset,
        before,
        snapshot(asset),
        site,
    )
    return asset


@transaction.atomic
def archive_asset(scope, actor, asset):
    scope.require_roles("admin", "manager")
    Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    asset = locked_active_asset(scope, asset.pk)
    if Asset.objects.filter(parent=asset, archived_at__isnull=True).exists():
        raise Conflict({"asset": "Archive or reparent active children first"})
    before = snapshot(asset)
    asset.archived_at = timezone.now()
    asset.save(update_fields=["archived_at", "updated_at"])
    audit(scope, actor, "asset.archived", asset, before, snapshot(asset), asset.site)


@transaction.atomic
def create_reference(scope, actor, model, data):
    scope.require_roles("admin")
    values = dict(data)
    site = None
    if model is FunctionalLocation:
        site = scope.site(values.pop("site_id"))
        parent_id = values.pop("parent_id", None)
        values["site"] = site
        values["parent"] = (
            related(FunctionalLocation, scope, parent_id, site) if parent_id else None
        )
    obj = model(tenant=scope.tenant, **values)
    if model is Site:
        obj.is_synthetic = scope.tenant.is_synthetic
    obj.full_clean(validate_unique=False, validate_constraints=False)
    obj.save()
    audit(
        scope,
        actor,
        "reference.created",
        obj,
        after={"code": obj.code, "name": obj.name},
        site=site or (obj if model is Site else None),
    )
    return obj


def validate_grant(scope, role, site_ids):
    if scope.role == "admin":
        pass
    elif scope.role == "manager" and role in {"engineer", "technician", "requester", "auditor"}:
        pass
    else:
        raise PermissionDenied("You cannot grant this role")
    if len(site_ids) != len(set(site_ids)):
        raise ValidationError({"site_ids": "Duplicate sites are not allowed"})
    sites = [scope.site(value) for value in site_ids]
    if role != "admin" and not sites:
        raise ValidationError({"site_ids": "At least one permitted site is required"})
    if role == "admin" and sites:
        raise ValidationError({"site_ids": "Admins have tenant-wide access; omit site grants"})
    return sites


@transaction.atomic
def invite(scope, actor, email, role, site_ids):
    scope.require_roles("admin", "manager")
    Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    sites = validate_grant(scope, role, site_ids)
    email = email.strip().lower()
    if Membership.objects.filter(
        tenant=scope.tenant, user__email__iexact=email, is_active=True
    ).exists():
        raise Conflict({"email": "User is already a member"})
    if Invitation.objects.filter(
        tenant=scope.tenant, email=email, accepted_at__isnull=True, expires_at__gt=timezone.now()
    ).exists():
        raise Conflict({"email": "An unexpired invitation already exists"})
    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        tenant=scope.tenant,
        email=email,
        role_id=role,
        invited_by=actor,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(hours=24),
    )
    for site in sites:
        InvitationSite.objects.create(tenant=scope.tenant, invitation=invitation, site=site)
    audit(
        scope,
        actor,
        "membership.invited",
        invitation,
        after={"role": role, "site_ids": [str(s.pk) for s in sites]},
    )
    link = f"{settings.FRONTEND_URL}/accept-invite#token={token}"
    if not settings.DEVELOPMENT_INVITE_LINKS:
        # Delivery is attempted before commit; failure rolls back the invitation.
        # Idempotent outbox delivery is a later hardening item.
        try:
            send_mail(
                "Your MaintainIQ invitation",
                f"Accept within 24 hours: {link}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 - never expose SMTP credentials/errors
            raise ValidationError(
                {"email": "Invitation delivery failed; retry or contact the administrator"}
            ) from exc
    return invitation, link if settings.DEVELOPMENT_INVITE_LINKS else None


def invitation_for(token, lock=False):
    qs = Invitation.objects.select_related("tenant", "role", "invited_by")
    if lock:
        qs = qs.select_for_update(of=("self",))
    try:
        invitation = qs.get(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
            tenant__is_active=True,
        )
        inviter = Membership.objects.select_related("tenant", "role").get(
            tenant=invitation.tenant,
            user=invitation.invited_by,
            is_active=True,
            user__is_active=True,
        )
        validate_grant(
            Scope(inviter), invitation.role_id, list(invitation.sites.values_list("id", flat=True))
        )
        return invitation
    except (Invitation.DoesNotExist, Membership.DoesNotExist, ValidationError, PermissionDenied):
        raise ValidationError(
            {"token": "Invitation is invalid, expired, consumed or no longer authorized"}
        ) from None


@transaction.atomic
def accept_invitation(token, full_name, password):
    invitation = invitation_for(token, lock=True)
    user = User.objects.filter(email__iexact=invitation.email).first()
    if user:
        if not user.is_active or not user.check_password(password):
            raise PermissionDenied("For an existing account, enter its current password")
    else:
        user = User(email=invitation.email, first_name=full_name)
        validate_password(password, user)
        user.set_password(password)
        user.save()
    membership, created = Membership.objects.get_or_create(
        tenant=invitation.tenant, user=user, defaults={"role_id": invitation.role_id}
    )
    if not created:
        raise Conflict(
            {
                "membership": "This account already belongs to the organization; ask its admin to update access"
            }
        )
    for site in invitation.sites.all():
        MembershipSite.objects.create(tenant=invitation.tenant, membership=membership, site=site)
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at", "updated_at"])
    audit(
        Scope(membership),
        user,
        "membership.accepted",
        membership,
        after={"role": membership.role_id},
    )
    return user


@transaction.atomic
def update_membership(scope, actor, membership, data):
    scope.require_roles("admin")
    Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    sites = validate_grant(scope, data["role"], data["site_ids"])
    if membership.user_id == actor.pk and (data["role"] != "admin" or not data["is_active"]):
        raise Conflict({"role": "Admins cannot demote or disable their own membership"})
    before = {"role": membership.role_id, "is_active": membership.is_active}
    membership.role_id = data["role"]
    membership.is_active = data["is_active"]
    membership.save()
    membership.site_grants.all().delete()
    for site in sites:
        MembershipSite.objects.create(tenant=scope.tenant, membership=membership, site=site)
    audit(
        scope,
        actor,
        "membership.updated",
        membership,
        before,
        {"role": membership.role_id, "is_active": membership.is_active},
    )
    return membership


@transaction.atomic
def onboard(name, slug, email, password):
    user = User(email=email.strip().lower(), first_name="Organization administrator")
    validate_password(password, user)
    if User.objects.filter(email__iexact=email).exists():
        raise DjangoValidationError(
            "Existing accounts must be onboarded through an authenticated invitation"
        )
    user.set_password(password)
    user.save()
    tenant = Tenant.objects.create(name=name, slug=slug)
    membership = Membership.objects.create(tenant=tenant, user=user, role_id="admin")
    audit(Scope(membership), user, "tenant.created", tenant, after={"name": name})
    return tenant


@transaction.atomic
def reset_password(uid: str, token: str, password: str) -> None:
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode

    try:
        identifier = UUID(urlsafe_base64_decode(uid).decode())
        user = User.objects.select_for_update().get(pk=identifier, is_active=True)
    except (User.DoesNotExist, ValueError, UnicodeDecodeError):
        raise ValidationError({"token": "Invalid or expired reset link"}) from None
    if not default_token_generator.check_token(user, token):
        raise ValidationError({"token": "Invalid or expired reset link"})
    validate_password(password, user)
    user.set_password(password)
    user.save(update_fields=["password"])
    for membership in Membership.objects.filter(user=user, is_active=True).select_related(
        "tenant", "role"
    ):
        audit(Scope(membership), user, "account.password_reset", user)


@transaction.atomic
def update_organization(scope, actor, data):
    scope.require_roles("admin")
    tenant = Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    before = {name: getattr(tenant, name) for name in ["name", "timezone", "currency"]}
    for name, value in data.items():
        setattr(tenant, name, value)
    tenant.full_clean()
    tenant.save()
    audit(
        scope,
        actor,
        "tenant.updated",
        tenant,
        before,
        {name: getattr(tenant, name) for name in ["name", "timezone", "currency"]},
    )
    return tenant


@transaction.atomic
def update_reference(scope, actor, obj, data):
    scope.require_roles("admin")
    Tenant.objects.select_for_update().get(pk=scope.tenant.pk)
    before = {"code": obj.code, "name": obj.name}
    values = dict(data)
    if isinstance(obj, FunctionalLocation):
        if values.get("site_id", obj.site_id) != obj.site_id:
            raise ValidationError({"site_id": "Location site is immutable in M1"})
        values.pop("site_id", None)
        if "parent_id" in values:
            identifier = values.pop("parent_id")
            parent = (
                related(FunctionalLocation, scope, identifier, obj.site) if identifier else None
            )
            ancestor = parent
            visited = set()
            while ancestor:
                if ancestor.pk == obj.pk or ancestor.pk in visited or len(visited) >= 100:
                    raise ValidationError(
                        {
                            "parent_id": "Location hierarchy would contain a cycle or exceed its limit"
                        }
                    )
                visited.add(ancestor.pk)
                ancestor = ancestor.parent
            values["parent"] = parent
        before["parent_id"] = str(obj.parent_id) if obj.parent_id else None
    for name, value in values.items():
        setattr(obj, name, value)
    obj.full_clean(validate_unique=False, validate_constraints=False)
    obj.save()
    after = {"code": obj.code, "name": obj.name}
    if isinstance(obj, FunctionalLocation):
        after["parent_id"] = str(obj.parent_id) if obj.parent_id else None
    site = obj if isinstance(obj, Site) else getattr(obj, "site", None)
    audit(scope, actor, "reference.updated", obj, before, after, site)
    return obj
