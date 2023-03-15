from django.db import transaction
from django.db.models import Q
from pulpcore.plugin.models import RepositoryVersion

from pulp_ansible.app.models import (
    CollectionVersion,
    CollectionVersionSignature,
    AnsibleCollectionDeprecated,
    CollectionVersionMark,
    AnsibleNamespaceMetadata,
    AnsibleRepository,
)

from pulpcore.plugin.tasking import add_and_remove

from .signature import sign


@transaction.atomic
def copy_content(config):
    """
    Copy content from one repo to another in a single transaction.

    This should be an iterable of dictionaries, with each dictionary containing the following keys:

        * source_repo_version: The RepositoryVersion pk
        * dest_repo: The pk of the `AnsibleRepository` pk to copy content into. This repository will
            receive the new RepositoryVersion with the copied content.
        * `content`: An optional key that if specified should contain a list of pks to copy. These
            specified keys must be members of the `source_repo_version`. If unspecified all content
            from the `source_repo_version` will be copied to the `dest_repo`.

    Args:
        config (iterable): The config that identifies the `source_repo_version`, `dest_repo`, and
            and `content`.

    """

    def process_entry(entry):
        source_repo_version = RepositoryVersion.objects.get(pk=entry["source_repo_version"])
        dest_repo = AnsibleRepository.objects.get(pk=entry["dest_repo"])

        dest_version_provided = bool(entry.get("dest_base_version"))
        if dest_version_provided:
            dest_repo_version = RepositoryVersion.objects.get(pk=entry["dest_base_version"])
        else:
            dest_repo_version = dest_repo.latest_version()

        if entry.get("content") is not None:
            content_filter = Q(pk__in=entry.get("content"))
        else:
            content_filter = Q()

        return (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_filter,
            dest_version_provided,
        )

    for entry in config:
        (
            source_repo_version,
            dest_repo_version,
            dest_repo,
            content_filter,
            dest_version_provided,
        ) = process_entry(entry)

        content_to_copy = source_repo_version.content.filter(content_filter)

        base_version = dest_repo_version if dest_version_provided else None
        with dest_repo.new_version(base_version=base_version) as new_version:
            new_version.add_content(content_to_copy)


def copy_collection(cv_pk_list, src_repo_pk, dest_repo_list):
    """
    Copy a list of collection versions and all of it's related contents into a
    list of destination repositories.
    """
    src_repo = AnsibleRepository.objects.get(pk=src_repo_pk)
    collection_versions = CollectionVersion.objects.filter(pk__in=cv_pk_list)

    content_types = src_repo.content.values_list("pulp_type", flat=True).distinct()
    source_pks = src_repo.content.values_list("pk", flat=True)

    content = cv_pk_list

    # collection signatures
    if "ansible.collection_signature" in content_types:
        signatures_pks = CollectionVersionSignature.objects.filter(
            signed_collection__in=cv_pk_list, pk__in=source_pks
        ).values_list("pk", flat=True)
        if signatures_pks:
            content.extend(signatures_pks)

    # collection version mark
    if "ansible.collection_mark" in content_types:
        marks_pks = CollectionVersionMark.objects.filter(
            marked_collection__in=cv_pk_list, pk__in=source_pks
        ).values_list("pk", flat=True)
        if marks_pks:
            content.extend(marks_pks)

    # namespace metadata
    namespaces = {x.namespace for x in collection_versions}
    namespaces_pks = AnsibleNamespaceMetadata.objects.filter(
        pk__in=source_pks,
        name__in=list(namespaces),
    ).values_list("pk", flat=True)
    if namespaces_pks:
        content.extend(namespaces_pks)

    # collection deprecation
    for cv in collection_versions:
        if "ansible.collection_deprecation" in content_types:
            deprecations_pks = AnsibleCollectionDeprecated.objects.filter(
                pk__in=source_pks,
                namespace=cv.namespace,
                name=cv.name,
            ).values_list("pk", flat=True)
            if deprecations_pks:
                content.extend(deprecations_pks)

    for pk in dest_repo_list:
        add_and_remove(repository_pk=pk, add_content_units=content, remove_content_units=[])


def move_collection(cv_pk_list, src_repo_pk, dest_repo_list):
    """
    Copy a collection and all of it's contents into a list of destination repositories
    """
    copy_collection(cv_pk_list, src_repo_pk, dest_repo_list)

    # No need to remove anything other than the collection version because everything
    # else will get handled by AnsibleRepository.finalize_repo_version()
    add_and_remove(repository_pk=src_repo_pk, add_content_units=[], remove_content_units=cv_pk_list)


def copy_or_move_and_sign(copy_or_move, signing_service_pk=None, **move_task_kwargs):
    if copy_or_move == "copy":
        copy_collection(**move_task_kwargs)
    else:
        move_collection(**move_task_kwargs)

    if signing_service_pk:
        for pk in move_task_kwargs["dest_repo_list"]:
            sign(
                signing_service_href=signing_service_pk,
                repository_href=pk,
                content_hrefs=move_task_kwargs["cv_pk_list"],
            )
