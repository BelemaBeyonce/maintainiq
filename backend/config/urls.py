from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from core.views import (
    AcceptInviteView,
    AssetViewSet,
    AuditViewSet,
    CategoryViewSet,
    ContextView,
    CsrfView,
    DashboardView,
    HealthView,
    InspectInviteView,
    InviteView,
    LocationViewSet,
    LoginView,
    LogoutView,
    MembershipDetailView,
    MembershipListView,
    OrganizationView,
    ResetConfirmView,
    ResetRequestView,
    SiteViewSet,
)

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("sites", SiteViewSet, basename="site")
router.register("categories", CategoryViewSet, basename="category")
router.register("locations", LocationViewSet, basename="location")
router.register("audit-events", AuditViewSet, basename="audit")
urlpatterns = [
    path("api/organization/", OrganizationView.as_view()),
    path("api/auth/password-reset/", ResetRequestView.as_view()),
    path("api/auth/password-reset/confirm/", ResetConfirmView.as_view()),
    path("api/auth/csrf/", CsrfView.as_view()),
    path("api/auth/login/", LoginView.as_view()),
    path("api/auth/logout/", LogoutView.as_view()),
    path("api/auth/context/", ContextView.as_view()),
    path("api/invitations/", InviteView.as_view()),
    path("api/auth/invitations/inspect/", InspectInviteView.as_view()),
    path("api/auth/invitations/accept/", AcceptInviteView.as_view()),
    path("api/memberships/", MembershipListView.as_view()),
    path("api/memberships/<uuid:pk>/", MembershipDetailView.as_view()),
    path("api/dashboard/", DashboardView.as_view()),
    path("api/health/", HealthView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/", include(router.urls)),
]
