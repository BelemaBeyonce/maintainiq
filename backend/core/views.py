import csv
import io
from uuid import UUID

from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Asset, AssetCategory, AuditEvent, FunctionalLocation, Membership, Site
from .scope import scope_for, scoped_assets
from .serializers import (
    AcceptInput,
    AssetSerializer,
    AuditSerializer,
    CategorySerializer,
    InviteInput,
    LocationSerializer,
    LoginInput,
    MembershipInput,
    OrganizationInput,
    ResetConfirmInput,
    ResetRequestInput,
    SiteSerializer,
    TokenInput,
)
from .services import (
    accept_invitation,
    archive_asset,
    create_reference,
    invitation_for,
    invite,
    save_asset,
    update_membership,
)

CSRF_HEADER = [
    OpenApiParameter(
        "X-CSRFToken",
        str,
        OpenApiParameter.HEADER,
        description="For mutations, use the token returned by GET /api/auth/csrf/; session cookies are sent by the same-origin browser.",
    )
]
TENANT_HEADERS = [
    OpenApiParameter("X-Tenant-ID", UUID, OpenApiParameter.HEADER, required=True),
    *CSRF_HEADER,
]


class LoginThrottle(AnonRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.META.get("REMOTE_ADDR", "unknown"),
        }


class OnboardingThrottle(LoginThrottle):
    scope = "onboarding"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(parameters=CSRF_HEADER)
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(request=LoginInput, responses={200: dict})
    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=data.validated_data["email"].strip().lower(),
            password=data.validated_data["password"],
        )
        if user is None:
            return Response(
                {
                    "error": {
                        "code": "invalid_credentials",
                        "message": "Invalid email or password",
                        "details": {},
                        "request_id": request.request_id,
                    }
                },
                status=401,
            )
        login(request, user)
        return Response({"id": str(user.pk), "email": user.email, "name": user.get_full_name()})


@extend_schema(parameters=CSRF_HEADER)
class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=204)


class ContextView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        memberships = (
            Membership.objects.filter(user=request.user, is_active=True, tenant__is_active=True)
            .select_related("tenant", "role")
            .order_by("tenant__name")
        )
        from .scope import Scope

        return Response(
            {
                "user": {
                    "id": str(request.user.pk),
                    "email": request.user.email,
                    "name": request.user.get_full_name(),
                },
                "organizations": [
                    {
                        "id": str(m.tenant_id),
                        "name": m.tenant.name,
                        "role": m.role_id,
                        "is_synthetic": m.tenant.is_synthetic,
                        "sites": SiteSerializer(Scope(m).sites(), many=True).data,
                    }
                    for m in memberships
                ],
            }
        )


class InviteView(APIView):
    @extend_schema(
        request=InviteInput,
        responses={201: dict},
        parameters=[OpenApiParameter("X-Tenant-ID", UUID, OpenApiParameter.HEADER, required=True)],
    )
    def post(self, request):
        scope = scope_for(request)
        data = InviteInput(data=request.data)
        data.is_valid(raise_exception=True)
        invitation, link = invite(scope, request.user, **data.validated_data)
        result = {
            "id": str(invitation.pk),
            "expires_at": invitation.expires_at,
            "delivery": "development_link" if link else "email",
        }
        if link:
            result["accept_url"] = link
        return Response(result, status=201)


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(parameters=CSRF_HEADER)
class InspectInviteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OnboardingThrottle]

    @extend_schema(request=TokenInput, responses={200: dict})
    def post(self, request):
        data = TokenInput(data=request.data)
        data.is_valid(raise_exception=True)
        inv = invitation_for(data.validated_data["token"])
        return Response({"organization": inv.tenant.name, "email": inv.email, "role": inv.role_id})


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(parameters=CSRF_HEADER)
class AcceptInviteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OnboardingThrottle]

    @extend_schema(request=AcceptInput, responses={201: dict})
    def post(self, request):
        data = AcceptInput(data=request.data)
        data.is_valid(raise_exception=True)
        user = accept_invitation(**data.validated_data)
        return Response(
            {"email": user.email, "message": "Invitation accepted. Sign in to continue."},
            status=201,
        )


@extend_schema(parameters=TENANT_HEADERS)
class MembershipView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        scope = scope_for(request)
        scope.require_roles("admin")
        qs = (
            Membership.objects.filter(tenant=scope.tenant)
            .select_related("user", "role")
            .order_by("user__email")[:100]
        )
        return Response(
            [
                {
                    "id": str(m.pk),
                    "email": m.user.email,
                    "role": m.role_id,
                    "is_active": m.is_active,
                    "site_ids": [str(s.site_id) for s in m.site_grants.all()],
                }
                for m in qs
            ]
        )

    @extend_schema(request=MembershipInput, responses={200: dict})
    def patch(self, request, pk):
        scope = scope_for(request)
        scope.require_roles("admin")
        try:
            membership = Membership.objects.get(pk=pk, tenant=scope.tenant)
        except Membership.DoesNotExist:
            raise Http404 from None
        data = MembershipInput(data=request.data)
        data.is_valid(raise_exception=True)
        result = update_membership(scope, request.user, membership, data.validated_data)
        return Response(
            {"id": str(result.pk), "role": result.role_id, "is_active": result.is_active}
        )


@extend_schema(parameters=TENANT_HEADERS)
class ReferenceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    def perform_create(self, serializer):
        serializer.instance = create_reference(
            scope_for(self.request), self.request.user, self.model, serializer.validated_data
        )

    def perform_update(self, serializer):
        from .services import update_reference

        serializer.instance = update_reference(
            scope_for(self.request),
            self.request.user,
            serializer.instance,
            serializer.validated_data,
        )


class SiteViewSet(ReferenceViewSet):
    model = Site
    serializer_class = SiteSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Site.objects.none()
        return scope_for(self.request).sites()


class CategoryViewSet(ReferenceViewSet):
    model = AssetCategory
    serializer_class = CategorySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AssetCategory.objects.none()
        return AssetCategory.objects.filter(tenant=scope_for(self.request).tenant)


class LocationViewSet(ReferenceViewSet):
    model = FunctionalLocation
    serializer_class = LocationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FunctionalLocation.objects.none()
        scope = scope_for(self.request)
        qs = FunctionalLocation.objects.filter(tenant=scope.tenant, site__in=scope.sites())
        site = self.request.query_params.get("site")
        if site:
            qs = qs.filter(site=scope.site(site))
        return qs


@extend_schema(parameters=TENANT_HEADERS)
class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Asset.objects.none()
        scope = scope_for(self.request)
        include = self.request.query_params.get("include_archived", "false")
        if include not in {"true", "false"}:
            raise ValidationError({"include_archived": "Use true or false"})
        qs = scoped_assets(scope, include_archived=include == "true")
        for key in ["site", "category"]:
            value = self.request.query_params.get(key)
            if value:
                if key == "site":
                    qs = qs.filter(site=scope.site(value))
                else:
                    try:
                        qs = qs.filter(category_id=UUID(value))
                    except ValueError:
                        raise ValidationError({"category": "Invalid category identifier"}) from None
        for key, choices in [
            ("status", {"active", "standby", "out_of_service"}),
            ("criticality", {"low", "medium", "high", "critical"}),
        ]:
            value = self.request.query_params.get(key)
            if value:
                if value not in choices:
                    raise ValidationError({key: "Invalid filter value"})
                qs = qs.filter(**{key: value})
        term = self.request.query_params.get("search", "").strip()
        if len(term) > 100:
            raise ValidationError({"search": "Search is limited to 100 characters"})
        if term:
            qs = qs.filter(
                Q(tag__icontains=term)
                | Q(name__icontains=term)
                | Q(manufacturer__icontains=term)
                | Q(serial_number__icontains=term)
            )
        return qs

    def perform_create(self, serializer):
        serializer.instance = save_asset(
            scope_for(self.request), self.request.user, serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = save_asset(
            scope_for(self.request),
            self.request.user,
            serializer.validated_data,
            serializer.instance,
        )

    def perform_destroy(self, instance):
        archive_asset(scope_for(self.request), self.request.user, instance)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        scope = scope_for(request)
        scope.require_roles("admin", "manager", "engineer", "technician", "auditor")
        asset = self.get_object()
        events = AuditEvent.objects.filter(
            tenant=scope.tenant, site__in=scope.sites(), object_id=asset.pk, entity_type="Asset"
        )
        page = self.paginate_queryset(events)
        return self.get_paginated_response(AuditSerializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="export", pagination_class=None)
    def export(self, request):
        scope = scope_for(request)
        scope.require_roles("admin", "manager", "engineer", "auditor")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["tag", "name", "site", "category", "status", "criticality", "synthetic", "archived_at"]
        )

        def safe(value):
            text = str(value)
            return (
                "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
            )

        for asset in self.get_queryset().iterator(chunk_size=500):
            writer.writerow(
                [
                    safe(v)
                    for v in [
                        asset.tag,
                        asset.name,
                        asset.site.name,
                        asset.category.name,
                        asset.status,
                        asset.criticality,
                        asset.is_synthetic,
                        asset.archived_at.isoformat() if asset.archived_at else "",
                    ]
                ]
            )
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="maintainiq-assets.csv"'
        response["Cache-Control"] = "no-store"
        return response


@extend_schema(parameters=TENANT_HEADERS)
class AuditViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditEvent.objects.none()
        scope = scope_for(self.request)
        scope.require_roles("admin", "manager", "engineer", "auditor")
        qs = AuditEvent.objects.filter(tenant=scope.tenant).select_related("actor")
        if scope.role != "admin":
            qs = qs.filter(site__in=scope.sites())
        site = self.request.query_params.get("site")
        if site:
            qs = qs.filter(site=scope.site(site))
        return qs


@extend_schema(parameters=TENANT_HEADERS)
class DashboardView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        scope = scope_for(request)
        qs = scoped_assets(scope, include_archived=True)
        site = request.query_params.get("site")
        if site:
            qs = qs.filter(site=scope.site(site))
        active = qs.filter(archived_at__isnull=True)
        return Response(
            {
                "total_assets": active.count(),
                "archived_assets": qs.filter(archived_at__isnull=False).count(),
                "critical_assets": active.filter(criticality="critical").count(),
                "status_counts": list(
                    active.values("status").annotate(count=Count("id")).order_by("status")
                ),
                "synthetic": scope.tenant.is_synthetic,
            }
        )


class HealthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict, 503: dict})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - sanitized readiness response
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ready"})


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(parameters=CSRF_HEADER)
class ResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OnboardingThrottle]

    @extend_schema(request=ResetRequestInput, responses={202: dict})
    def post(self, request):
        from .serializers import ResetRequestInput
        from .tasks import send_password_reset

        data = ResetRequestInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            send_password_reset.delay(data.validated_data["email"].strip().lower())
        except Exception:  # noqa: BLE001 - same response regardless account/queue state
            import logging

            logging.getLogger("maintainiq").warning("password_reset_queue_unavailable")
        return Response(
            {"message": "If the account exists, reset instructions will be sent."}, status=202
        )


@method_decorator(csrf_protect, name="dispatch")
@extend_schema(parameters=CSRF_HEADER)
class ResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OnboardingThrottle]

    @extend_schema(request=ResetConfirmInput, responses={200: dict})
    def post(self, request):
        from .services import reset_password

        data = ResetConfirmInput(data=request.data)
        data.is_valid(raise_exception=True)
        reset_password(**data.validated_data)
        return Response({"message": "Password changed. Sign in with your new password."})


@extend_schema(parameters=TENANT_HEADERS)
class OrganizationView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        tenant = scope_for(request).tenant
        return Response(
            {
                "id": str(tenant.pk),
                "name": tenant.name,
                "timezone": tenant.timezone,
                "currency": tenant.currency,
                "is_synthetic": tenant.is_synthetic,
            }
        )

    @extend_schema(request=OrganizationInput, responses={200: dict})
    def patch(self, request):
        from .services import update_organization

        scope = scope_for(request)
        scope.require_roles("admin")
        data = OrganizationInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        tenant = update_organization(scope, request.user, data.validated_data)
        return Response(
            {
                "id": str(tenant.pk),
                "name": tenant.name,
                "timezone": tenant.timezone,
                "currency": tenant.currency,
                "is_synthetic": tenant.is_synthetic,
            }
        )


class MembershipListView(MembershipView):
    http_method_names = ["get", "head", "options"]


class MembershipDetailView(MembershipView):
    http_method_names = ["patch", "options"]
