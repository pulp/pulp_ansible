"""Tasks for CollectionVersionMark"""

from pulpcore.plugin.tasking import add_and_remove
from pulp_ansible.app.models import AnsibleRepository, CollectionVersion, CollectionVersionMark


def mark(repository_href, content_hrefs, value):
    """The mark task."""
    repository = AnsibleRepository.objects.get(pk=repository_href)
    content = _get_content_queryset(repository, content_hrefs)
    marks_in_repo = _get_list_of_marks_pk_in_repo(repository, content, value)

    marks_to_add = []
    for collection_version in content:
        # A mark for the same collection and value may exist in another repo.
        mark, _created = CollectionVersionMark.objects.get_or_create(
            marked_collection=collection_version, value=value
        )
        if mark.pk not in marks_in_repo:
            marks_to_add.append(mark.pk)

    add_and_remove(
        repository_pk=repository.pk,
        add_content_units=marks_to_add,
        remove_content_units=[],
    )


def unmark(repository_href, content_hrefs, value):
    """The unmark task."""
    repository = AnsibleRepository.objects.get(pk=repository_href)
    content = _get_content_queryset(repository, content_hrefs)
    marks_in_repo = _get_list_of_marks_pk_in_repo(repository, content, value)
    add_and_remove(
        repository_pk=repository.pk,
        add_content_units=[],
        remove_content_units=marks_in_repo,
    )


def _get_list_of_marks_pk_in_repo(repository, content, value):
    """Get all the marks from repo having value and content"""
    return (
        repository.latest_version()
        .content.filter(
            pulp_type=CollectionVersionMark.get_pulp_type(),
            ansible_collectionversionmark__value=value,
            ansible_collectionversionmark__marked_collection__in=content,
        )
        .values_list("pk", flat=True)
    )


def _get_content_queryset(repository, content_hrefs):
    """Return content queryset based on a repo and content hrefs"""
    if content_hrefs == ["*"]:
        content_in_latest_version = repository.latest_version().content.filter(
            pulp_type=CollectionVersion.get_pulp_type()
        )
        return CollectionVersion.objects.filter(pk__in=content_in_latest_version)
    return CollectionVersion.objects.filter(pk__in=content_hrefs)
