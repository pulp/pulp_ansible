from pulpcore.plugin.models import RepositoryContent
from django.db.models import OuterRef, Exists


# TODO: if this turns out to be a more efficient way to query repo version
# content, then this should be contributed to pulpcore
def filter_content_for_repo_version(qs, repo_version):
    """
    A more efficient way to query content in a repository version.

    Returns a the given queryset, but filtered to only include content
    from the specified repository version.

    qs: Content queryset. Must be a model that is or inherits from
        pulpcore.plugin.models.Content
    repo_version: repository version to return content from
    """
    in_repo_version_qs = RepositoryContent.objects.filter(
        repository=repo_version.repository,
        version_added__number__lte=repo_version.number,
        content__pk=OuterRef("pk"),
    ).exclude(version_removed__number__lte=repo_version.number)

    return qs.annotate(in_repo_version=Exists(in_repo_version_qs)).filter(in_repo_version=True)
