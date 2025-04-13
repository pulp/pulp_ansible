"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""

import datetime

import pytest

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)
from pulp_ansible.tests.functional.constants import TEST_COLLECTION_CONFIGS
from orionutils.generator import build_collection
from pulpcore.client.pulp_ansible import PulpAnsibleArtifactsCollectionsV3Api
from pulp_ansible.tests.functional.utils import monitor_task


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


class FullDependenciesSync(TestCaseUsingBindings, SyncHelpersMixin):
    """
    Collection sync tests for syncing collections and their dependencies.

    Dependency Trees:
    A               E
    |             /   \
    B            F     G
    |            |     |
    C         H(1-3)   D
    |
    D

    H has 5 versions, no dependencies
    """

    @classmethod
    def setUpClass(cls):
        """Set up class variables."""
        super().setUpClass()
        cls._build_and_publish_collections()

    @classmethod
    def tearDownClass(cls):
        """Tear down class variables."""
        cls.repo_api.delete(cls.repo.pulp_href)
        cls.distributions_api.delete(cls.distro.pulp_href)

    @classmethod
    def _build_and_publish_collections(cls):
        """Builds and publishes the collections to be used in this test."""
        from django.conf import settings

        cls.collections = []
        cls.repo, cls.distro = cls._create_empty_repo_and_distribution(cls(), cleanup=False)

        upload_api = PulpAnsibleArtifactsCollectionsV3Api(cls.client)
        for cfg in TEST_COLLECTION_CONFIGS:
            collection = build_collection("skeleton", config=cfg)
            upload_response = upload_api.create(cls.distro.base_path, collection.filename)
            api_root = settings.API_ROOT
            monitor_task("{}api/v3/tasks/{}/".format(api_root, upload_response.task[-37:-1]))
            cls.collections.append(collection)
        cls.distro.client_url += "api/"

    def test_simple_one_level_dependency(self):
        """Sync test.c which requires test.d."""
        body = gen_ansible_remote(
            url=self.distro.client_url,
            requirements_file="collections:\n  - test.c",
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)
        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        assert content.count == 2

    def test_simple_multi_level_dependency(self):
        """Sync test.a which should get the dependency chain: test.b -> test.c -> test.d."""
        body = gen_ansible_remote(
            url=self.distro.client_url,
            requirements_file="collections:\n  - test.a",
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        assert content.count == 4

    def test_complex_one_level_dependency(self):
        """Sync test.f which should get 3 versions of test.h."""
        body = gen_ansible_remote(
            url=self.distro.client_url,
            requirements_file="collections:\n  - test.f",
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        assert content.count == 4

    def test_complex_multi_level_dependency(self):
        """Sync test.e which should get test.f, test.d, test.g and 3 versions of test.h."""
        body = gen_ansible_remote(
            url=self.distro.client_url,
            requirements_file="collections:\n  - test.e",
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        assert content.count == 7


@pytest.mark.skip("Skipped until fixture metadata has a published date")
@pytest.mark.parallel
def test_optimized_sync(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
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


@pytest.mark.parallel
def test_sync_progress_report(
    ansible_bindings,
    ansible_repo,
    ansible_collection_remote_factory,
    monitor_task,
):
    """Checks that the progress report messages are correct."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
        signed_only=False,
    )
    body = {"remote": remote.pulp_href}
    task = monitor_task(
        ansible_bindings.RepositoriesAnsibleApi.sync(ansible_repo.pulp_href, body).task
    )

    progress_reports = task.progress_reports
    assert len(progress_reports) == 5
    messages = {pr.message for pr in progress_reports}

    assert messages == {
        "Parsing CollectionVersion Metadata",
        "Parsing Namespace Metadata",
        "Downloading Artifacts",
        # "Downloading Docs Blob",  # This reuses the "Downloading Artifacts" name.
        "Associating Content",
    }

    for pr in progress_reports:
        if pr.message == "Parsing CollectionVersion Metadata":
            assert pr.total == pr.done
        if pr.message == "Parsing Namespace Metadata":
            assert pr.total == pr.done == 1
