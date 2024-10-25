"""Tests related to sync ansible plugin collection content type."""

import pytest

from pulp_ansible.tests.functional.utils import randstr
from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    GALAXY_ANSIBLE_BASE_URL,
)


@pytest.mark.parallel
def test_tags_filter(
    ansible_bindings,
    ansible_collection_remote_factory,
    ansible_sync_factory,
):
    """Filter CollectionVersions by using the tags filter.

    This test targets the following issue:

    * `Pulp #5571 <https://pulp.plan.io/issues/5571>`_

    Do the following:

    1. Create a repository, and a remote.
    2. Sync the remote.
    3. Attempt to filter the CollectionVersions by different tags

    Note that the testing.k8s_demo_collection collection has tags 'k8s' and 'kubernetes'.
    """
    ansible_sync_factory(
        remote=ansible_collection_remote_factory(
            url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS
        ).pulp_href
    )

    # filter collection versions by tags
    params = {"tags": "nada"}
    collections = ansible_bindings.ContentCollectionVersionsApi.list(**params).results
    assert len(collections) == 0, collections

    params = {"tags": "k8s"}
    collections = ansible_bindings.ContentCollectionVersionsApi.list(**params).results
    assert len(collections) == 1, collections

    params = {"tags": "k8s,kubernetes"}
    collections = ansible_bindings.ContentCollectionVersionsApi.list(**params).results
    assert len(collections) == 1, collections

    params = {"tags": "nada,k8s"}
    collections = ansible_bindings.ContentCollectionVersionsApi.list(**params).results
    assert len(collections) == 0, collections


@pytest.mark.parallel
def test_content_unit_lifecycle(ansible_bindings, build_and_upload_collection, monitor_task):
    """Create content unit."""
    attrs = {"namespace": randstr(), "name": "squeezer", "version": "0.0.9"}
    collection_artifact, content_unit_href = build_and_upload_collection(config=attrs)

    # Read a content unit by its href.
    content_unit = ansible_bindings.ContentCollectionVersionsApi.read(content_unit_href)
    for key, val in attrs.items():
        assert content_unit.to_dict()[key] == val

    # Read a content unit by its pkg_id.
    page = ansible_bindings.ContentCollectionVersionsApi.list(
        namespace=content_unit.namespace, name=content_unit.name
    )
    assert page.count == 1
    assert page.results[0] == content_unit

    # Attempt to update a content unit using HTTP PATCH.
    # This HTTP method is not supported and a HTTP exception is expected.
    with pytest.raises(AttributeError) as exc_info:
        ansible_bindings.ContentCollectionVersionsApi.partial_update(
            content_unit_href, name="testing"
        )
    msg = "object has no attribute 'partial_update'"
    assert msg in exc_info.value.args[0]

    # Attempt to update a content unit using HTTP PUT.
    # This HTTP method is not supported and a HTTP exception is expected.
    with pytest.raises(AttributeError) as exc_info:
        ansible_bindings.ContentCollectionVersionsApi.update(content_unit_href, {"name": "testing"})
    msg = "object has no attribute 'update'"
    assert msg in exc_info.value.args[0]

    # Attempt to delete a content unit using HTTP DELETE.
    # This HTTP method is not supported and a HTTP exception is expected.
    with pytest.raises(AttributeError) as exc_info:
        ansible_bindings.ContentCollectionVersionsApi.delete(content_unit_href)
    msg = "object has no attribute 'delete'"
    assert msg in exc_info.value.args[0]

    # Attempt to create duplicate collection.
    create_task = monitor_task(
        ansible_bindings.ContentCollectionVersionsApi.create(file=collection_artifact.filename).task
    )
    assert content_unit_href in create_task.created_resources
