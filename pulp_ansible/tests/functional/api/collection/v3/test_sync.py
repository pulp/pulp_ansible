"""Tests related to sync ansible plugin collection content type."""

import pytest


REQUIREMENTS_FILE = "collections:\n  - testing.k8s_demo_collection"


@pytest.fixture(scope="class")
def galaxy_remote(ansible_collection_remote_factory):
    return ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file=REQUIREMENTS_FILE,
        sync_dependencies=False,
    )


@pytest.fixture(scope="class")
def galaxy_repository(ansible_bindings, monitor_task, ansible_repository_factory, galaxy_remote):
    repository = ansible_repository_factory(remote=galaxy_remote.pulp_href)
    result = ansible_bindings.RepositoriesAnsibleApi.sync(repository.pulp_href, {})
    monitor_task(result.task)
    return repository


@pytest.fixture(scope="class")
def galaxy_distribution(ansible_distribution_factory, galaxy_repository):
    """
    Provide a distribution that serves the testing.k8s_demo_collection.
    """
    return ansible_distribution_factory(repository=galaxy_repository)


class TestSync:
    def test_synced_collection_is_findable(self, ansible_bindings, galaxy_distribution):
        collection = ansible_bindings.PulpAnsibleApiV3CollectionsApi.read(
            "k8s_demo_collection", "testing", galaxy_distribution.base_path
        )

        assert collection.name == "k8s_demo_collection"
        assert collection.namespace == "testing"

    @pytest.mark.parametrize("requirements_file", (None, REQUIREMENTS_FILE))
    @pytest.mark.parametrize("mirror", (True, False))
    def test_sync_collection_from_pulp(
        self,
        ansible_bindings,
        monitor_task,
        ansible_repository_factory,
        ansible_collection_remote_factory,
        galaxy_distribution,
        requirements_file,
        mirror,
    ):
        remote = ansible_collection_remote_factory(
            url=galaxy_distribution.client_url,
            requirements_file=requirements_file,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        repository = ansible_repository_factory(remote=remote.pulp_href)
        result = ansible_bindings.RepositoriesAnsibleApi.sync(
            repository.pulp_href, {"mirror": mirror}
        )
        monitor_task(result.task)

        content = ansible_bindings.ContentCollectionVersionsApi.list(
            repository_version=f"{repository.pulp_href}versions/1/"
        )
        assert len(content.results) >= 1

    @pytest.mark.parametrize("mirror", (True, False))
    def test_sync_absent_collection_from_pulp_fails(
        self,
        ansible_bindings,
        monitor_task,
        ansible_repository_factory,
        ansible_collection_remote_factory,
        galaxy_distribution,
        mirror,
    ):
        remote = ansible_collection_remote_factory(
            url=galaxy_distribution.client_url,
            requirements_file="collections:\n  - absent.not_present",
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        repository = ansible_repository_factory(remote=remote.pulp_href)
        result = ansible_bindings.RepositoriesAnsibleApi.sync(
            repository.pulp_href, {"mirror": mirror}
        )
        message = "Collection absent.not_present does not exist on"
        with pytest.raises(Exception) as exc_info:
            monitor_task(result.task)
        assert message in exc_info.value.task.error["description"]

    @pytest.mark.parametrize("mirror", (True, False))
    def test_resync_is_noop(
        self,
        ansible_bindings,
        monitor_task,
        ansible_repository_factory,
        ansible_collection_remote_factory,
        galaxy_distribution,
        mirror,
    ):
        remote = ansible_collection_remote_factory(
            url=galaxy_distribution.client_url,
            requirements_file=REQUIREMENTS_FILE,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        repository = ansible_repository_factory(remote=remote.pulp_href)
        result = ansible_bindings.RepositoriesAnsibleApi.sync(
            repository.pulp_href, {"mirror": mirror}
        )
        monitor_task(result.task)

        # Resync
        result = ansible_bindings.RepositoriesAnsibleApi.sync(
            repository.pulp_href, {"mirror": mirror, "optimize": True}
        )
        task = monitor_task(result.task)
        msg = f"no-op: {galaxy_distribution.client_url} did not change since last sync"
        messages = " ".join([r.message for r in task.progress_reports])
        assert msg in messages

    def test_updating_requirements_file_resets_last_synced(
        self, ansible_bindings, monitor_task, galaxy_repository, galaxy_remote
    ):
        repository = ansible_bindings.RepositoriesAnsibleApi.read(galaxy_repository.pulp_href)
        assert repository.last_synced_metadata_time is not None

        response = ansible_bindings.RemotesCollectionApi.partial_update(
            galaxy_remote.pulp_href, {"requirements_file": "collections:\n  - ansible.posix"}
        )
        monitor_task(response.task)

        repository = ansible_bindings.RepositoriesAnsibleApi.read(galaxy_repository.pulp_href)
        assert repository.last_synced_metadata_time is None
