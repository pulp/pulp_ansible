"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""
import datetime
import os

import pytest
import unittest
from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)
from pulp_ansible.tests.functional.constants import TEST_COLLECTION_CONFIGS
from orionutils.generator import build_collection
from pulpcore.client.pulp_ansible import PulpAnsibleArtifactsCollectionsV3Api
from pulp_ansible.tests.functional.utils import (  # noqa
    monitor_task,
    set_up_module as setUpModule,
)


class MirrorTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Sync the ansible plugin collections content type."""

    def test_sync_supports_mirror_option_true(self):
        """Sync multiple remotes into the same repo with mirror as `True`."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - robertdebock.ansible_development_environment",
            sync_dependencies=False,
        )
        remote_a = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_a.pulp_href)

        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote_b = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_b.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote_a)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}1/")
        repo = self._sync_repo(repo, remote=remote_b.pulp_href, mirror=True)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}2/")

        # Assert more CollectionVersion are present in the first sync than the second
        if repo.retain_repo_versions and repo.retain_repo_versions > 1:
            content_version_one = self.cv_api.list(
                repository_version=f"{repo.pulp_href}versions/1/"
            )
            self.assertGreaterEqual(len(content_version_one.results), 3)
        content_version_two = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/2/")
        self.assertEqual(len(content_version_two.results), 1)

    def test_sync_supports_mirror_option_false(self):
        """Sync multiple remotes into the same repo with mirror as `False`."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - robertdebock.ansible_development_environment",
            sync_dependencies=False,
        )
        remote_a = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_a.pulp_href)

        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote_b = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_b.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote_a)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}1/")
        repo = self._sync_repo(repo, remote=remote_b.pulp_href, mirror=False)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}2/")

        # Assert more CollectionVersion are present in the first sync than the second
        if repo.retain_repo_versions and repo.retain_repo_versions > 1:
            content_version_one = self.cv_api.list(
                repository_version=f"{repo.pulp_href}versions/1/"
            )
            self.assertGreaterEqual(len(content_version_one.results), 3)
        content_version_two = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/2/")
        self.assertEqual(len(content_version_two.results), 4)

    def test_sync_mirror_defaults_to_false(self):
        """Sync multiple remotes into the same repo to ensure mirror defaults to `False`."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - robertdebock.ansible_development_environment",
            sync_dependencies=False,
        )
        remote_a = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_a.pulp_href)

        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote_b = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote_b.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote_a)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}1/")
        repo = self._sync_repo(repo, remote=remote_b.pulp_href)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}2/")

        # Assert more CollectionVersion are present in the first sync than the second
        if repo.retain_repo_versions and repo.retain_repo_versions > 1:
            content_version_one = self.cv_api.list(
                repository_version=f"{repo.pulp_href}versions/1/"
            )
            self.assertGreaterEqual(len(content_version_one.results), 3)
        content_version_two = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/2/")
        self.assertEqual(len(content_version_two.results), 4)


class UniqueCollectionsTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Collection sync tests for collections with unique properties."""

    def test_sync_collection_with_long_tag(self):
        """Sync a collection that is known to have "longer" tag information."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - ibm.ibm_zos_core",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 14)

    def test_sync_collection_with_dot_slash_in_manifest(self):
        """Sync a collection that has a ./Manifest.json instead of Manifest.json."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - rshad.collection_demo",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 6)

    def test_sync_collection_with_stranger_version_numbers_to_check_comparisons(self):
        """Sync a collection that has strange version numbers and ensure it syncs correctly."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - brightcomputing.bcm",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 5)


@unittest.skip("Skip until S3 error has been discovered.")
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
        cls.collections = []
        cls.repo, cls.distro = cls._create_empty_repo_and_distribution(cls(), cleanup=False)

        upload_api = PulpAnsibleArtifactsCollectionsV3Api(cls.client)
        for cfg in TEST_COLLECTION_CONFIGS:
            collection = build_collection("skeleton", config=cfg)
            upload_response = upload_api.create(cls.distro.base_path, collection.filename)
            api_root = os.environ.get("PULP_API_ROOT", "/pulp/")
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
        self.assertEqual(content.count, 2)

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
        self.assertEqual(content.count, 4)

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
        self.assertEqual(content.count, 4)

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
        self.assertEqual(content.count, 7)

    def test_v2_simple_dependency(self):
        """Checks that the dependency resolution works on v2 api codepath."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - pulp.pulp_installer",
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/", name="posix")
        self.assertNotEqual(content.count, 0)


@pytest.mark.skip("Skipped until fixture metadata has a published date")
@pytest.mark.parallel
def test_optimized_sync(
    ansible_repo_api_client,
    ansible_remote_collection_api_client,
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
    monitor_task(ansible_repo_api_client.sync(repository.pulp_href, {}).task)
    repository = ansible_repo_api_client.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is not None
    monitor_task(ansible_repo_api_client.sync(repository.pulp_href, {"optimize": True}).task)
    # TODO CHECK IF SYNC WAS OPTIMIZED
    monitor_task(
        ansible_repo_api_client.sync(
            repository.pulp_href, {"remote": remote2.pulp_href, "optimize": True}
        ).task
    )
    repository = ansible_repo_api_client.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is None
    # TODO CHECK IF SYNC WAS NOT OPTIMIZED


@pytest.mark.parallel
def test_last_synced_metadata_time(
    ansible_repo_api_client,
    ansible_remote_collection_api_client,
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
        ansible_repo_api_client.partial_update(
            repository.pulp_href, {"last_synced_metadata_time": "2000-01-01 00:00"}
        ).task
    )
    repository = ansible_repo_api_client.read(repository.pulp_href)
    assert repository.last_synced_metadata_time == datetime.datetime(
        2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    monitor_task(
        ansible_remote_collection_api_client.partial_update(
            remote1.pulp_href, {"signed_only": True}
        ).task
    )
    repository = ansible_repo_api_client.read(repository.pulp_href)
    assert repository.last_synced_metadata_time is None
