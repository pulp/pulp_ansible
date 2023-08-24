from django.db.models import Q, OuterRef, Subquery, CharField
from pulpcore.plugin.models import RepositoryVersion, RepositoryContent, Task
from django.db.models.functions import Cast, JSONObject


def filter_content_for_repo_version(qs, repo_version):
    """
    Returns the given queryset, but filtered to only include content
    from the specified repository version.

    qs: Content queryset. Must be a model that is or inherits from
        pulpcore.plugin.models.Content
    repo_version: repository version to return content from

    This generally seems to be faster than repo_version.get_content()
    """

    repo_version_qs = RepositoryVersion.objects.filter(
        repository=repo_version.repository_id, number__lte=repo_version.number
    ).values_list("pk")

    f = (
        Q(repository=repo_version.repository_id)
        & Q(version_added__in=repo_version_qs)
        & Q(Q(version_removed=None) | ~Q(version_removed__in=repo_version_qs))
    )
    content_rel = RepositoryContent.objects.filter(f)

    return qs.filter(pk__in=content_rel.values_list("content_id"))


def get_queryset_annotated_with_last_sync_task(qs):
    last_task = (
        Task.objects.filter(
            name__contains="sync",
            reserved_resources_record__icontains=Cast(OuterRef("pk"), output_field=CharField()),
        )
        .values(
            json=JSONObject(
                pk="pk",
                state="state",
                pulp_created="pulp_created",
                finished_at="finished_at",
                error="error",
            )
        )
        .order_by("-pulp_created")[:1]
    )

    return qs.annotate(last_sync_task=Subquery(last_task))
