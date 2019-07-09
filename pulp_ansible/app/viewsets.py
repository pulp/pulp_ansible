from collections import defaultdict
from gettext import gettext as _
from packaging.version import parse

from django.contrib.postgres.search import SearchQuery
from django.db import IntegrityError
from django.db.models import fields as db_fields
from django.db.models.expressions import F, Func
from django_filters import filters
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from pulpcore.plugin.exceptions import DigestValidationError
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    ContentFilter,
    ContentViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    RemoteViewSet,
)

from .models import (
    AnsibleDistribution,
    AnsibleRemote,
    CollectionVersion,
    CollectionRemote,
    Role,
    Tag,
)
from .serializers import (
    AnsibleDistributionSerializer,
    AnsibleRemoteSerializer,
    CollectionVersionSerializer,
    CollectionRemoteSerializer,
    CollectionOneShotSerializer,
    RoleSerializer,
    TagSerializer,
)
from .tasks.collections import sync as collection_sync
from .tasks.collections import import_collection
from .tasks.synchronizing import synchronize as role_sync


class RoleFilter(ContentFilter):
    """
    FilterSet for Roles.
    """

    class Meta:
        model = Role
        fields = ["name", "namespace", "version"]


class RoleViewSet(ContentViewSet):
    """
    ViewSet for Role.
    """

    endpoint_name = "roles"
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilter


class CollectionVersionFilter(ContentFilter):
    """
    FilterSet for Ansible Collections.
    """

    namespace = filters.CharFilter(field_name="namespace")
    name = filters.CharFilter(field_name="name")
    latest = filters.BooleanFilter(field_name="latest", method="filter_latest")
    q = filters.CharFilter(field_name="q", method="filter_by_q")

    def filter_by_q(self, queryset, name, value):
        """
        Full text search provided by the 'q' option.

        Args:
            queryset: The query to add the additional full-text search filtering onto
            name: The name of the option specified, i.e. 'q'
            value: The string to search on

        Returns:
            The Django queryset that was passed in, additionally filtered by full-text search.

        """
        search_query = SearchQuery(value)
        qs = queryset.filter(search_vector=search_query)
        ts_rank_fn = Func(
            F("search_vector"),
            search_query,
            32,  # RANK_NORMALIZATION = 32
            function="ts_rank",
            output_field=db_fields.FloatField(),
        )
        return qs.annotate(rank=ts_rank_fn).order_by("-rank")

    def filter_latest(self, queryset, name, value):
        """
        If the value of 'latest' is True, include only the latest Collection version in the results.

        Args:
            queryset: The already-formed queryset for modification
            name: The name of the parameter, 'latest'
            value: The value of the argument. This is checked if 'True' or not.

        Returns:
            Queryset with latest collections included if value is True.

        """
        if not value:
            return queryset

        namespace_name_dict = defaultdict(lambda: defaultdict(list))
        for collection in queryset.all():
            version_entry = (parse(collection.version), collection.pk)
            namespace_name_dict[collection.namespace][collection.name].append(version_entry)

        latest_pks = []
        for namespace, name_dict in namespace_name_dict.items():
            for name, version_list in name_dict.items():
                version_list.sort(reverse=True)
                latest_pk = version_list[0][1]
                latest_pks.append(latest_pk)

        return queryset.filter(pk__in=latest_pks)

    class Meta:
        model = CollectionVersion
        fields = ["namespace", "name", "version"]


class CollectionVersionViewSet(ContentViewSet):
    """
    ViewSet for Ansible Collection.
    """

    endpoint_name = "collections"
    queryset = CollectionVersion.objects.prefetch_related("_artifacts")
    serializer_class = CollectionVersionSerializer
    filterset_class = CollectionVersionFilter


class AnsibleRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Ansible Remotes.
    """

    endpoint_name = "ansible"
    queryset = AnsibleRemote.objects.all()
    serializer_class = AnsibleRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Ansible content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get("repository")
        mirror = serializer.validated_data.get("mirror", False)
        result = enqueue_with_reservation(
            role_sync,
            [repository, remote],
            kwargs={"remote_pk": remote.pk, "repository_pk": repository.pk, "mirror": mirror},
        )
        return OperationPostponedResponse(result, request)


class CollectionRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Collection Remotes.
    """

    endpoint_name = "collection"
    queryset = CollectionRemote.objects.all()
    serializer_class = CollectionRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Collection content.",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a Collection sync task.
        """
        collection_remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get("repository")
        mirror = serializer.validated_data.get("mirror", False)
        kwargs = {
            "remote_pk": collection_remote.pk,
            "repository_pk": repository.pk,
            "mirror": mirror,
        }

        result = enqueue_with_reservation(
            collection_sync, [repository, collection_remote], kwargs=kwargs
        )
        return OperationPostponedResponse(result, request)


class CollectionUploadViewSet(viewsets.ViewSet):
    """
    ViewSet for One Shot Collection Upload.

    Args:
        file@: package to upload
    """

    serializer_class = CollectionOneShotSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Create an artifact and trigger an asynchronous task to create "
        "Collection content from it.",
        operation_summary="Upload a collection",
        operation_id="upload_collection",
        request_body=CollectionOneShotSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """
        Dispatch a Collection creation task.
        """
        serializer = CollectionOneShotSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        expected_digests = {}
        if serializer.validated_data["sha256"]:
            expected_digests["sha256"] = serializer.validated_data["sha256"]
        try:
            artifact = Artifact.init_and_validate(
                serializer.validated_data["file"], expected_digests=expected_digests
            )
        except DigestValidationError:
            raise serializers.ValidationError(
                _("The provided sha256 value does not match the sha256 of the uploaded file.")
            )

        try:
            artifact.save()
        except IntegrityError:
            raise serializers.ValidationError(_("Artifact already exists."))

        async_result = enqueue_with_reservation(
            import_collection, [str(artifact.pk)], kwargs={"artifact_pk": artifact.pk}
        )

        return OperationPostponedResponse(async_result, request)


class AnsibleDistributionViewSet(BaseDistributionViewSet):
    """
    ViewSet for Ansible Distributions.
    """

    endpoint_name = "ansible"
    queryset = AnsibleDistribution.objects.all()
    serializer_class = AnsibleDistributionSerializer


class TagViewSet(NamedModelViewSet, mixins.ListModelMixin):
    """
    ViewSet for Tag models.
    """

    endpoint_name = "pulp_ansible/tags"
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
