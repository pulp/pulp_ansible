"""Tests for version: 'latest' support in collection sync."""

import pytest


@pytest.mark.parallel
def test_sync_latest_version(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync with version: 'latest' should download only one collection version."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file='collections:\n  - name: community.crypto\n    version: "latest"',
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count == 1


@pytest.mark.parallel
def test_sync_latest_does_not_affect_wildcard(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync with version: '*' should still download all versions."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file='collections:\n  - name: community.molecule\n    version: "*"',
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count > 1


@pytest.mark.parallel
def test_sync_latest_does_not_affect_pinned(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync with an explicit pinned version should still work."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file='collections:\n  - name: community.crypto\n    version: "2.0.0"',
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count == 1
    assert content.results[0].version == "2.0.0"


@pytest.mark.parallel
def test_sync_latest_mixed_requirements(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync with mixed version specifiers: one latest, one pinned."""
    requirements = (
        "collections:\n"
        '  - name: community.molecule\n    version: "latest"\n'
        '  - name: community.crypto\n    version: "2.0.0"'
    )
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file=requirements,
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    versions = {f"{c.namespace}.{c.name}-{c.version}" for c in content.results}
    assert content.count == 2
    assert "community.crypto-2.0.0" in versions
