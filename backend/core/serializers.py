from rest_framework import serializers

from .models import Asset, AssetCategory, AuditEvent, FunctionalLocation, Site


class StrictMixin:
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        readonly = {name for name in data if name in self.fields and self.fields[name].read_only}
        if unknown or readonly:
            raise serializers.ValidationError(
                {name: "Unknown or read-only field" for name in unknown | readonly}
            )
        return super().to_internal_value(data)


class InputSerializer(StrictMixin, serializers.Serializer):
    pass


class LoginInput(InputSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class InviteInput(InputSerializer):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(
        choices=["admin", "manager", "engineer", "technician", "requester", "auditor"]
    )
    site_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True, max_length=100
    )


class AcceptInput(InputSerializer):
    token = serializers.CharField(min_length=40, max_length=100)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )


class TokenInput(InputSerializer):
    token = serializers.CharField(min_length=40, max_length=100)


class MembershipInput(InputSerializer):
    role = serializers.ChoiceField(
        choices=["admin", "manager", "engineer", "technician", "requester", "auditor"]
    )
    site_ids = serializers.ListField(child=serializers.UUIDField(), max_length=100)
    is_active = serializers.BooleanField(default=True)


class SiteSerializer(StrictMixin, serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "code", "name", "is_synthetic"]
        read_only_fields = ["id", "is_synthetic"]


class CategorySerializer(StrictMixin, serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ["id", "code", "name"]
        read_only_fields = ["id"]


class LocationSerializer(StrictMixin, serializers.ModelSerializer):
    site_id = serializers.UUIDField()
    parent_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = FunctionalLocation
        fields = ["id", "site_id", "parent_id", "code", "name"]
        read_only_fields = ["id"]


class AssetSerializer(StrictMixin, serializers.ModelSerializer):
    site_id = serializers.UUIDField()
    category_id = serializers.UUIDField()
    functional_location_id = serializers.UUIDField(required=False, allow_null=True)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    location_code = serializers.CharField(
        source="functional_location.code", read_only=True, default=""
    )

    class Meta:
        model = Asset
        fields = [
            "id",
            "site_id",
            "site_name",
            "category_id",
            "category_name",
            "functional_location_id",
            "location_code",
            "parent_id",
            "tag",
            "name",
            "manufacturer",
            "model",
            "serial_number",
            "status",
            "criticality",
            "description",
            "is_synthetic",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_synthetic", "archived_at", "created_at", "updated_at"]

    def validate_tag(self, value):
        return value.strip().upper()


class AuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", default="System")

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "site_id",
            "actor_name",
            "action",
            "entity_type",
            "object_id",
            "before",
            "after",
            "timestamp",
        ]


class ResetRequestInput(InputSerializer):
    email = serializers.EmailField(max_length=254)


class ResetConfirmInput(InputSerializer):
    uid = serializers.CharField(max_length=100)
    token = serializers.CharField(max_length=100)
    password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )


class OrganizationInput(InputSerializer):
    name = serializers.CharField(max_length=160)
    timezone = serializers.CharField(max_length=80)
    currency = serializers.RegexField(r"^[A-Z]{3}$")

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Select a valid IANA timezone") from None
        return value
