"""Tests related to Galaxy V3 serializers."""

from pulpcore.client.pulp_ansible import (
    AnsibleRepositorySyncURL,
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
from pulp_ansible.tests.functional.utils import tasks


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

        requirements1 = """
        collections:
            - name: "pulp.squeezer"
              version: "0.0.7"
        """

        requirements2 = """
        collections:
            - name: "pulp.squeezer"
              version: "0.0.17"
        """

        # sync the first version ...
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements1,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        collections = self.collections_api.list(distribution.base_path)

        original_highest_version = collections.data[0].highest_version["version"]
        original_updated_at = collections.data[0].updated_at

        original_total_versions = self.collections_versions_v3api.list(
            "squeezer", "pulp", distribution.base_path
        ).meta.count

        # sync the second version ...
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements2,
            sync_dependencies=False,
        )
        self.remote_collection_api.update(remote.pulp_href, body)
        repository_sync_data = AnsibleRepositorySyncURL(remote=remote.pulp_href, optimize=True)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        task = tasks.read(sync_response.task)
        self.assertEqual(task.state, "completed")

        # enumerate new data after 2nd sync ...
        collections = self.collections_api.list(distribution.base_path)
        highest_version = collections.data[0].highest_version["version"]
        updated_at = collections.data[0].updated_at
        total_versions = self.collections_versions_v3api.list(
            "squeezer", "pulp", distribution.base_path
        ).meta.count

        self.assertEqual(original_highest_version, "0.0.7")
        self.assertEqual(highest_version, "0.0.17")
        self.assertEqual(original_total_versions, 1)
        self.assertEqual(total_versions, 2)
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
