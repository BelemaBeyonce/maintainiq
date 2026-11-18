from dataclasses import dataclass
from uuid import UUID

from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Membership, Site


@dataclass(frozen=True)
class Scope:
    membership: Membership

    @property
    def tenant(self):
        return self.membership.tenant

    @property
    def role(self):
        return self.membership.role_id

    def sites(self):
        qs = Site.objects.filter(tenant=self.tenant)
        return qs if self.role == "admin" else qs.filter(membershipsite__membership=self.membership)

    def require_roles(self, *roles):
        if self.role not in roles:
            raise PermissionDenied("Your role does not permit this action")

    def site(self, identifier):
        try:
            return self.sites().get(pk=UUID(str(identifier)))
        except (Site.DoesNotExist, ValueError, TypeError):
            raise ValidationError(
                {"site": "Site is unavailable in your authorized scope"}
            ) from None


def scope_for(request):
    if hasattr(request, "tenant_scope"):
        return request.tenant_scope
    try:
        tenant_id = UUID(request.headers.get("X-Tenant-ID", ""))
    except ValueError:
        raise ValidationError({"tenant": "Select an organization using X-Tenant-ID"}) from None
    try:
        membership = Membership.objects.select_related("tenant", "role").get(
            user=request.user, tenant_id=tenant_id, is_active=True, tenant__is_active=True
        )
    except Membership.DoesNotExist:
        raise Http404("Organization unavailable") from None
    request.tenant_scope = Scope(membership)
    return request.tenant_scope


def scoped_assets(scope, include_archived=False):
    from .models import Asset

    qs = Asset.objects.filter(tenant=scope.tenant, site__in=scope.sites()).select_related(
        "site", "category", "functional_location", "parent"
    )
    return qs if include_archived else qs.filter(archived_at__isnull=True)
