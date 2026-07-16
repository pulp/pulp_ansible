"""Tests for sync_highest_versions field on CollectionRemote."""

import pytest


@pytest.mark.parallel
def test_sync_highest_versions_one(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Setting sync_highest_versions=1 should download only one collection version."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - name: community.crypto",
        sync_dependencies=False,
        sync_highest_versions=1,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count == 1


@pytest.mark.parallel
def test_sync_highest_versions_null_syncs_all(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Setting sync_highest_versions=None (default) should download all versions."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - name: community.molecule",
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count > 1


@pytest.mark.parallel
def test_sync_highest_versions_does_not_affect_pinned(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Explicit pinned versions should still work regardless of sync_highest_versions."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file='collections:\n  - name: community.crypto\n    version: "2.0.0"',
        sync_dependencies=False,
        sync_highest_versions=1,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count == 1
    assert content.results[0].version == "2.0.0"


@pytest.mark.parallel
def test_sync_highest_versions_with_range(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """sync_highest_versions should limit results within a version range."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file='collections:\n  - name: community.crypto\n    version: ">=1.0.0,<3.0.0"',
        sync_dependencies=False,
        sync_highest_versions=1,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count == 1
