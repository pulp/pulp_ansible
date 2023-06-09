from django.db.models import Q
from pulpcore.plugin.models import RepositoryVersion, RepositoryContent


def filter_content_for_repo_version(qs, repo_version):
    """
    Returns a the given queryset, but filtered to only include content
    from the specified repository version.

    qs: Content queryset. Must be a model that is or inherits from
        pulpcore.plugin.models.Content
    repo_version: repository version to return content from

    This generally seems to be faster than repo_version.get_content()
    """

    repo_version_qs = RepositoryVersion.objects.filter(
        repository=repo_version.repository, number__lte=repo_version.number
    ).values_list("pk")

    f = Q(version_added__in=repo_version_qs) & Q(
        Q(version_removed=None) | ~Q(version_removed__in=repo_version_qs)
    )
    content_rel = RepositoryContent.objects.filter(f)

    return qs.filter(pk__in=content_rel.values_list("content_id"))
