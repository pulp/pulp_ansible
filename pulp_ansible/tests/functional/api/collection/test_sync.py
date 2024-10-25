"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""

import datetime

import pytest

from pulp_ansible.tests.functional.utils import randstr


@pytest.mark.parallel
def test_sync_supports_mirror_option_true(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync multiple remotes into the same repo with mirror as `True`."""
    remote_a = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    remote_b = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote_a.pulp_href)
    assert repository.latest_version_href == f"{repository.versions_href}1/"
    repository = ansible_sync_factory(repository, remote=remote_b.pulp_href, mirror=True)
    assert repository.latest_version_href == f"{repository.versions_href}2/"

    # Assert more CollectionVersion are present in the first sync than the second
    if repository.retain_repo_versions and repository.retain_repo_versions > 1:
        content_version_one = ansible_bindings.ContentCollectionVersionsApi.list(
            repository_version=f"{repository.pulp_href}versions/1/"
        )
        assert content_version_one.count >= 3
    content_version_two = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/2/"
    )
    assert content_version_two.count == 1


@pytest.mark.parallel
def test_sync_supports_mirror_option_false(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync multiple remotes into the same repo with mirror as `False`."""
    remote_a = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    remote_b = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote_a.pulp_href)
    assert repository.latest_version_href == f"{repository.versions_href}1/"
    repository = ansible_sync_factory(repository, remote=remote_b.pulp_href, mirror=False)
    assert repository.latest_version_href == f"{repository.versions_href}2/"

    # Assert more CollectionVersion are present in the second sync than the first
    if repository.retain_repo_versions and repository.retain_repo_versions > 1:
        content_version_one = ansible_bindings.ContentCollectionVersionsApi.list(
            repository_version=f"{repository.pulp_href}versions/1/"
        )
        assert content_version_one.count >= 3
    content_version_two = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/2/"
    )
    assert content_version_two.count == 4


@pytest.mark.parallel
def test_sync_mirror_defaults_to_false(
    ansible_bindings, ansible_collection_remote_factory, ansible_sync_factory
):
    """Sync multiple remotes into the same repo to ensure mirror defaults to `False`."""
    remote_a = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    remote_b = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote_a.pulp_href)
    assert repository.latest_version_href == f"{repository.versions_href}1/"
    repository = ansible_sync_factory(repository, remote=remote_b.pulp_href)
    assert repository.latest_version_href == f"{repository.versions_href}2/"

    # Assert more CollectionVersion are present in the second sync than the first
    if repository.retain_repo_versions and repository.retain_repo_versions > 1:
        content_version_one = ansible_bindings.ContentCollectionVersionsApi.list(
            repository_version=f"{repository.pulp_href}versions/1/"
        )
        assert content_version_one.count >= 3
    content_version_two = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/2/"
    )
    assert content_version_two.count == 4


@pytest.mark.parallel
@pytest.mark.parametrize(
    "collection,old_galaxy,sync_dependencies,min_count",
    [
        pytest.param("ibm.ibm_zos_core", False, False, 14, id="with_long_tag"),
        pytest.param("rshad.collection_demo", False, False, 6, id="with_dot_slash_in_manifest"),
        pytest.param("brightcomputing.bcm", True, False, 5, id="with_strange_version_numbers"),
        pytest.param(
            "pulp.pulp_installer",
            False,
            True,
            5,
            id="simple_dependency",
            marks=[pytest.mark.timeout(1800)],  # TODO This test takes too much time!
        ),
    ],
)
def test_sync_collection_with_specialities(
    ansible_bindings,
    collection,
    old_galaxy,
    sync_dependencies,
    min_count,
    ansible_collection_remote_factory,
    ansible_sync_factory,
):
    """Sync a collection that is known to be special."""
    remote = ansible_collection_remote_factory(
        url=(
            "https://old-galaxy.ansible.com/api/"
            if old_galaxy
            else "https://galaxy.ansible.com/api/"
        ),
        requirements_file=f"collections:\n  - {collection}",
        sync_dependencies=sync_dependencies,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)

    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{repository.pulp_href}versions/1/"
    )
    assert content.count >= min_count


class TestFullDependenciesSync:
    @pytest.fixture(scope="class")
    def distribution_with_dependencies(
        self,
        ansible_repo_factory,
        ansible_distribution_factory,
        build_and_upload_collection,
    ):
        """
        Collections with dependencies in a repository.
        """

        # Dependency Graph:
        #     E     A  I
        #     |\    |  |\
        #     F G   B  J K
        #     |  \  |   \|
        #  H(1-3) \ C    L
        #          \|
        #           D

        namespace = randstr()
        TEST_COLLECTION_CONFIGS = [
            {"namespace": namespace, "name": "a", "dependencies": {f"{namespace}.b": "*"}},
            {"namespace": namespace, "name": "b", "dependencies": {f"{namespace}.c": "*"}},
            {"namespace": namespace, "name": "c", "dependencies": {f"{namespace}.d": "*"}},
            {"namespace": namespace, "name": "d"},
            {
                "namespace": namespace,
                "name": "e",
                "dependencies": {f"{namespace}.f": "*", f"{namespace}.g": "*"},
            },
            {"namespace": namespace, "name": "f", "dependencies": {f"{namespace}.h": "<=3.0.0"}},
            {"namespace": namespace, "name": "g", "dependencies": {f"{namespace}.d": "*"}},
            {"namespace": namespace, "name": "h", "version": "1.0.0"},
            {"namespace": namespace, "name": "h", "version": "2.0.0"},
            {"namespace": namespace, "name": "h", "version": "3.0.0"},
            {
                "namespace": namespace,
                "name": "i",
                "dependencies": {f"{namespace}.j": "*", f"{namespace}.k": "*"},
            },
            {"namespace": namespace, "name": "j", "dependencies": {f"{namespace}.l": "*"}},
            {"namespace": namespace, "name": "k", "dependencies": {f"{namespace}.l": "*"}},
            {"namespace": namespace, "name": "l"},
        ]
        repository = ansible_repo_factory()
        distribution = ansible_distribution_factory(
            repository=repository, pulp_labels={"namespace": namespace}
        )
        for config in TEST_COLLECTION_CONFIGS:
            build_and_upload_collection(repository, config={"namespace": namespace, **config})
        return distribution

    @pytest.mark.parametrize(
        "collection_name,expected_count",
        [
            pytest.param("d", 1, id="no_dependency"),
            pytest.param("c", 2, id="simple_one_level"),
            pytest.param("a", 4, id="simple_multi_level"),
            pytest.param("f", 4, id="complex_one_level"),
            pytest.param("e", 7, id="complex_multi_level"),
            pytest.param("i", 4, id="diamond_shaped"),
        ],
    )
    # Running this test in parallel leads to weird failures with upload.
    # @pytest.mark.parallel
    def test_dependency_sync(
        self,
        collection_name,
        expected_count,
        ansible_bindings,
        distribution_with_dependencies,
        ansible_collection_remote_factory,
        ansible_sync_factory,
    ):
        namespace = distribution_with_dependencies.pulp_labels["namespace"]
        remote = ansible_collection_remote_factory(
            url=distribution_with_dependencies.client_url,
            requirements_file=f"collections:\n  - {namespace}.{collection_name}",
            include_pulp_auth=True,
        )
        repository = ansible_sync_factory(remote=remote.pulp_href)

        content = ansible_bindings.ContentCollectionVersionsApi.list(
            repository_version=f"{repository.pulp_href}versions/1/"
        )
        assert content.count == expected_count


@pytest.mark.skip("Skipped until fixture metadata has a published date")
@pytest.mark.parallel
def test_optimized_sync(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    monitor_task,
):
    # TODO this test is incomplete and may not work
    remote1 = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
        signed_only=False,
    )
    remote2 = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
        signed_only=False,
    )
    repository = ansible_repo_factory(remote=remote1.pulp_href)
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sync(repository.pulp_href, {}).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is not None
    monitor_task(
        ansible_bindings.RepositoriesAnsibleApi.sync(repository.pulp_href, {"optimize": True}).task
    )
    # TODO CHECK IF SYNC WAS OPTIMIZED
    monitor_task(
        ansible_bindings.RepositoriesAnsibleApi.sync(
            repository.pulp_href, {"remote": remote2.pulp_href, "optimize": True}
        ).task
    )
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is None
    # TODO CHECK IF SYNC WAS NOT OPTIMIZED


@pytest.mark.parallel
def test_semver_sync(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    monitor_task,
):
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - anil_cm.terraform_provider",
        sync_dependencies=False,
        signed_only=False,
    )
    repository = ansible_repo_factory(remote=remote.pulp_href)
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sync(repository.pulp_href, {}).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    content = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=repository.latest_version_href
    )
    versions = {item.version for item in content.results}
    # If this fails check that it is still upstream!
    # TODO create a better local fixture to sync from.
    assert "0.0.1-rerelease+meta" in versions
    assert "0.0.0-rerelease+meta" in versions


@pytest.mark.parallel
def test_last_synced_metadata_time(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    monitor_task,
):
    remote1 = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
        signed_only=False,
    )
    repository = ansible_repo_factory(remote=remote1.pulp_href)
    monitor_task(
        ansible_bindings.RepositoriesAnsibleApi.partial_update(
            repository.pulp_href, {"last_synced_metadata_time": "2000-01-01 00:00"}
        ).task
    )
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    assert repository.last_synced_metadata_time == datetime.datetime(
        2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    monitor_task(
        ansible_bindings.RemotesCollectionApi.partial_update(
            remote1.pulp_href, {"signed_only": True}
        ).task
    )
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is None
