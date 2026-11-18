import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.full_clean(exclude=["password", "last_login"])
        user.save(using=self._db)
        return user


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_ci_unique")]


class Entity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(Entity):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    is_synthetic = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    timezone = models.CharField(max_length=80, default="Africa/Lagos")
    currency = models.CharField(max_length=3, default="NGN")


class Role(models.Model):
    code = models.CharField(primary_key=True, max_length=20)
    name = models.CharField(max_length=80)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    code__in=["admin", "manager", "engineer", "technician", "requester", "auditor"]
                ),
                name="valid_role_code",
            )
        ]


class TenantEntity(Entity):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class Membership(TenantEntity):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="membership_user_unique"),
            models.UniqueConstraint(fields=["id", "tenant"], name="membership_tenant_key"),
        ]


class Site(TenantEntity):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="site_code_unique"),
            models.UniqueConstraint(fields=["id", "tenant"], name="site_tenant_key"),
        ]
        ordering = ["name", "id"]


class MembershipSite(TenantEntity):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="site_grants")
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["membership", "site"], name="membership_site_unique")
        ]


class FunctionalLocation(TenantEntity):
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site", "code"], name="location_code_unique"),
            models.UniqueConstraint(fields=["id", "site", "tenant"], name="location_scope_key"),
        ]
        ordering = ["code", "id"]


class AssetCategory(TenantEntity):
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="category_code_unique"),
            models.UniqueConstraint(fields=["id", "tenant"], name="category_tenant_key"),
        ]
        ordering = ["name", "id"]


class Asset(TenantEntity):
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    functional_location = models.ForeignKey(
        FunctionalLocation, null=True, blank=True, on_delete=models.PROTECT
    )
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    tag = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=24,
        choices=[
            ("active", "Active"),
            ("standby", "Standby"),
            ("out_of_service", "Out of service"),
        ],
        default="active",
    )
    criticality = models.CharField(
        max_length=16,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        default="medium",
    )
    description = models.TextField(max_length=5000, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        ordering = ["tag", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "tag"], name="asset_tag_unique"),
            models.UniqueConstraint(fields=["id", "site", "tenant"], name="asset_scope_key"),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "standby", "out_of_service"]),
                name="asset_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(criticality__in=["low", "medium", "high", "critical"]),
                name="asset_valid_criticality",
            ),
            models.CheckConstraint(
                condition=~models.Q(id=models.F("parent_id")), name="asset_not_own_parent"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "site", "archived_at"], name="asset_scope_archive"),
            models.Index(fields=["tenant", "category"], name="asset_scope_category"),
        ]


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are append-only")

    def delete(self):
        raise ValidationError("Audit events are append-only")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    site = models.ForeignKey(Site, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=40)
    object_id = models.UUIDField()
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    objects = AppendOnlyQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are append-only")

    class Meta:
        ordering = ["-timestamp", "id"]
        indexes = [models.Index(fields=["tenant", "site", "timestamp"], name="audit_scope_time")]


class Invitation(TenantEntity):
    email = models.EmailField()
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True)
    sites = models.ManyToManyField(Site, through="InvitationSite")
    invited_by = models.ForeignKey(User, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "email"], name="invite_tenant_email")]
        constraints = [
            models.UniqueConstraint(fields=["id", "tenant"], name="invitation_tenant_key")
        ]


class InvitationSite(TenantEntity):
    invitation = models.ForeignKey(Invitation, on_delete=models.CASCADE)
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invitation", "site"], name="invitation_site_unique")
        ]
