"""Tests related to Galaxy V3 deprecation."""

import pytest


@pytest.mark.parallel
@pytest.mark.parametrize("repo_kwargs", [{}, {"retain_repo_versions": 1}])
def test_deprecation(
    ansible_bindings,
    ansible_collection_remote_factory,
    ansible_repo_factory,
    ansible_distribution_factory,
    ansible_sync_factory,
    monitor_task,
    repo_kwargs,
):
    """Test sync  sync."""
    # Sync down two collections into a repo
    requirements = (
        "collections:\n" "  - name: testing.k8s_demo_collection\n" "  - name: pulp.squeezer"
    )

    first_remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file=requirements,
        sync_dependencies=False,
    )

    first_repo = ansible_sync_factory(
        ansible_repo_factory(remote=first_remote.pulp_href, **repo_kwargs)
    )
    first_distribution = ansible_distribution_factory(repository=first_repo)

    # Assert the state of deprecated True for testing, False for pulp
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        first_distribution.base_path, namespace="testing"
    )
    assert collections.data[0].deprecated
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        first_distribution.base_path, namespace="pulp"
    )
    assert not collections.data[0].deprecated

    # Sync a second repo from the first, just the testing namespace
    requirements = "collections:\n" "  - name: testing.k8s_demo_collection"
    second_remote = ansible_collection_remote_factory(
        url=first_distribution.client_url,
        requirements_file=requirements,
        sync_dependencies=False,
        include_pulp_auth=True,
    )

    second_repo = ansible_sync_factory(
        ansible_repo_factory(remote=second_remote.pulp_href, **repo_kwargs)
    )
    second_distribution = ansible_distribution_factory(repository=second_repo)

    # Ensure the second remote received a deprecated=True for the testing namespace collection
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        second_distribution.base_path, namespace="testing"
    )
    assert collections.data[0].deprecated

    # Sync again to see if the deprecated state is kept.
    ansible_sync_factory(second_repo, optimize=False)
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        second_distribution.base_path, namespace="testing"
    )
    assert collections.data[0].deprecated

    # Update the requirements to sync down both collections this time
    requirements = (
        "collections:\n" "  - name: testing.k8s_demo_collection\n" "  - name: pulp.squeezer"
    )
    ansible_bindings.RemotesCollectionApi.partial_update(
        second_remote.pulp_href, {"requirements_file": requirements}
    )

    # Sync the second repo again
    second_repo = ansible_sync_factory(second_repo)

    # Assert the state of deprecated True for testing, False for pulp
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        second_distribution.base_path, namespace="testing"
    )
    assert collections.data[0].deprecated
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        second_distribution.base_path, namespace="pulp"
    )
    assert not collections.data[0].deprecated

    # Change the deprecated status for the testing collection on the original repo to False
    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.update(
            "k8s_demo_collection", "testing", first_distribution.base_path, {"deprecated": False}
        ).task
    )
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        first_distribution.base_path, namespace="testing"
    )
    assert not collections.data[0].deprecated

    # Sync the second repo again
    second_repo = ansible_sync_factory(second_repo)

    # Assert both collections show deprecated=False
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(
        second_distribution.base_path
    )
    assert len(collections.data) == 2, collections
    for collection in collections.data:
        assert not collection.deprecated
