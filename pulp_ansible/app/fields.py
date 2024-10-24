from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


@extend_schema_field(OpenApiTypes.OBJECT)
class JSONDictField(serializers.JSONField):
    """A drf JSONField override to force openapi schema to use 'object' type.

    Not strictly correct, but we relied on that for a long time.
    See: https://github.com/tfranzel/drf-spectacular/issues/1095
    """
