import json

from collections import OrderedDict

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import BadRequest

from drf_spectacular.utils import extend_schema_field

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from pulpcore.plugin.models.role import Role

from pulpcore.plugin.util import (
    assign_role,
    remove_role,
    get_groups_with_perms_attached_roles,
    get_perms_for_model,
)
from pulpcore.plugin.models import Group


class RelatedFieldsBaseSerializer(serializers.Serializer):
    """
    Serializer only returns fields specified in 'include_related' query param.

    This allows for fields that require more database queries to be optionally
    included in API responses, which lowers the load on the backend. This is
    intended as a way to include extra data in list views.

    Usage:

    This functions the same as DRF's base `serializers.Serializer` class with the
    exception that it will only return fields specified in the `?include_related=`
    query parameter.

    Example:

    MySerializer(RelatedFieldsBaseSerializer):
        foo = CharField()
        bar = CharField()

    MySerializer will return:

    {"foo": None} when called with `?include_related=foo` and {"foo": None, "bar" None}
    when called with `?include_related=foo&include_related=bar`.
    """

    def __init__(self, *args, **kwargs):
        # This should only be included as a sub serializer and shouldn't be used for
        # updating objects, so set read_only to true
        kwargs["read_only"] = True
        return super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        result = OrderedDict()
        fields = self._readable_fields
        request = self.context.get("request", None)
        if request:
            # TODO: Figure out how to make `include_related` show up in the open API spec
            include_fields = request.GET.getlist("include_related")

            if len(include_fields) > 0:
                for field in fields:
                    if field.field_name in include_fields:
                        result[field.field_name] = field.to_representation(instance)
        else:
            # When there is no request present, it usually means that the serializer is
            # being inspected by DRF spectacular to generate the open API spec. In that
            # case, this should act like a normal serializer.
            return super().to_representation(instance)

        return result


class MyPermissionsField(serializers.Serializer):
    def to_representation(self, original_obj):
        request = self.context.get("request", None)
        if request is None:
            return []
        user = request.user

        if original_obj._meta.proxy:
            obj = original_obj._meta.concrete_model.objects.get(pk=original_obj.pk)
        else:
            obj = original_obj

        my_perms = []
        for perm in get_perms_for_model(type(obj)).all():
            codename = "{}.{}".format(perm.content_type.app_label, perm.codename)
            if user.has_perm(codename) or user.has_perm(codename, obj):
                my_perms.append(codename)

        return my_perms


def set_object_group_roles(obj, new_groups):
    current_groups = get_groups_with_perms_attached_roles(obj, include_model_permissions=False)

    # remove the old roles
    for group in current_groups:
        if group in new_groups:
            new_groups.pop(group)
            continue
        for role in current_groups[group]:
            remove_role(role, group, obj)

    # add the new ones
    for group in new_groups:
        for role in new_groups[group]:
            try:
                assign_role(role, group, obj)
            except BadRequest:
                raise ValidationError(
                    detail={
                        "groups": _(
                            "Role {role} does not exist or does not "
                            "have any permissions related to this object."
                        ).format(role=role)
                    }
                )


class GroupFieldType(serializers.Serializer):
    """
    Group open api type
    """

    name = serializers.CharField(max_length=256, allow_blank=False)
    id = serializers.CharField(max_length=256, allow_blank=True, required=False)
    object_roles = serializers.ListField(child=serializers.CharField())


@extend_schema_field(GroupFieldType(many=True))
class GroupPermissionField(serializers.Field):
    def get_value(self, dictionary):
        data = dictionary.get(self.field_name, [])

        # The open api client sends data as a form request rather than json
        # because of the avatar URL. It converts a list like
        # [{"foo": "bar"}, {"bar": "foo"}] into "{'foo': 'bar'}, {'bar': 'foo'}"
        # This is a best effort attempt to capture that data and convert it into
        # valid JSON and then transform it into a list that the API can understand
        if isinstance(data, str):
            try:
                data = f"[{data}]".replace("'", '"')
                return json.loads(data)
            except json.decoder.JSONDecodeError:
                raise ValidationError(detail={"links": "Must be valid JSON"})

        return super().get_value(dictionary)

    def _validate_group(self, group_data):
        if "object_roles" not in group_data:
            raise ValidationError(detail={"groups": _("object_roles field is required")})

        if "id" not in group_data and "name" not in group_data:
            raise ValidationError(detail={"groups": _("id or name field is required")})

        roles = group_data["object_roles"]

        if not isinstance(roles, list):
            raise ValidationError(detail={"groups": _("object_roles must be a list of strings")})

        # validate that the permissions exist
        for role in roles:
            # TODO(newswangerd): Figure out how to make this one SQL query instead of
            # performing N queries for each permission
            if not Role.objects.filter(name=role).exists():
                raise ValidationError(detail={"groups": _("Role {} does not exist").format(role)})

    def to_representation(self, value):
        rep = []
        groups = get_groups_with_perms_attached_roles(
            value, include_model_permissions=False, for_concrete_model=True
        )
        for group in groups:
            rep.append({"id": group.id, "name": group.name, "object_roles": groups[group]})
        return rep

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise ValidationError(detail={"groups": _("Groups must be a list of group objects")})

        internal = {}
        for group_data in data:
            self._validate_group(group_data)
            group_filter = {}
            for field in group_data:
                if field in ("id", "name"):
                    group_filter[field] = group_data[field]
            try:
                group = Group.objects.get(**group_filter)
                if "object_permissions" in group_data:
                    internal[group] = group_data["object_permissions"]
                if "object_roles" in group_data:
                    internal[group] = group_data["object_roles"]
            except Group.DoesNotExist:
                raise ValidationError(
                    detail={
                        "groups": _("Group name=%s, id=%s does not exist")
                        % (group_data.get("name"), group_data.get("id"))
                    }
                )
            except ValueError:
                raise ValidationError(detail={"group": _("Invalid group name or ID")})

        return internal
