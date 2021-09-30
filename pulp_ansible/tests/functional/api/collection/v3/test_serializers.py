"""Tests related to Galaxy V3 serializers."""
from pulpcore.client.pulp_ansible import (
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RepositoriesAnsibleApi,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import SyncHelpersMixin, TestCaseUsingBindings
from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CollectionsV3TestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Test Collections V3 endpoint."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleApiV3CollectionsApi(cls.client)
        cls.collections_versions_api = ContentCollectionVersionsApi(cls.client)
        cls.collections_versions_v3api = PulpAnsibleApiV3CollectionsVersionsApi(cls.client)

    def test_v3_updated_at(self):
        """Test Collections V3 endpoint field: ``updated_at``."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - pulp.squeezer",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        collections = self.collections_api.list(distribution.base_path)

        original_highest_version = collections.data[0].highest_version["version"]
        original_updated_at = collections.data[0].updated_at

        versions = self.collections_versions_api.list(version="0.0.7")
        original_total_versions = self.collections_versions_v3api.list(
            "squeezer", "pulp", distribution.base_path
        ).meta.count

        data = {"remove_content_units": [versions.results[0].pulp_href]}
        response = self.repo_api.modify(repo.pulp_href, data)
        monitor_task(response.task)

        collections = self.collections_api.list(distribution.base_path)
        highest_version = collections.data[0].highest_version["version"]
        updated_at = collections.data[0].updated_at

        total_versions = self.collections_versions_v3api.list(
            "squeezer", "pulp", distribution.base_path
        ).meta.count

        self.assertEqual(highest_version, original_highest_version)
        self.assertEqual(original_total_versions, total_versions + 1)
        self.assertGreater(updated_at, original_updated_at)

    def test_v3_collection_version_from_synced_data(self):
        """Test Collection Versions V3 endpoint fields."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: cisco.nxos\n    version: 1.4.0",
            sync_dependencies=False,
        )

        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        version = self.collections_versions_v3api.read(
            "nxos", "cisco", distribution.base_path, "1.4.0"
        )

        self.assertEqual(version.requires_ansible, ">=2.9.10,<2.11")
        self.assertTrue("'name': 'README.md'" in str(version.files))
        self.assertEqual(version.manifest["collection_info"]["name"], "nxos")
