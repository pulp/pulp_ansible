"""Tests related to Galaxy V3 serializers."""
import unittest
from datetime import datetime

from pulpcore.client.pulp_ansible import (
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleGalaxyApiCollectionsApi,
    PulpAnsibleGalaxyApiV3VersionsApi,
    RepositoriesAnsibleApi,
    RepositorySyncURL,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote, monitor_task
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CollectionsV3TestCase(unittest.TestCase):
    """Test Collections V3 endpoint."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleGalaxyApiCollectionsApi(cls.client)
        cls.collections_versions_api = ContentCollectionVersionsApi(cls.client)
        cls.collections_versions_v3api = PulpAnsibleGalaxyApiV3VersionsApi(cls.client)

    def setUp(self):
        """Create distribution for V3."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.repo_href = repo.pulp_href
        requirements = "collections:\n  - name: pulp.pulp_installer"

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=requirements)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # Sync the repository.
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        distribution_url = monitor_task(distribution_create.task)
        distribution = self.distributions_api.read(distribution_url[0])
        self.base_path = distribution.base_path
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

    def test_v3_updated_at(self):
        """Test Collections V3 endpoint field: ``updated_at``."""
        repo = self.repo_api.read(self.repo_href)

        collections = self.collections_api.list(self.base_path)

        original_highest_version = collections.data[0].highest_version["version"]
        original_updated_at = datetime.strptime(
            collections.data[0].updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        versions = self.collections_versions_api.list(version="3.6.4")
        original_total_versions = self.collections_versions_v3api.list(
            "pulp_installer", "pulp", self.base_path
        ).meta["count"]

        data = {"remove_content_units": [versions.results[0].pulp_href]}
        response = self.repo_api.modify(repo.pulp_href, data)
        monitor_task(response.task)

        collections = self.collections_api.list(self.base_path)
        highest_version = collections.data[0].highest_version["version"]
        updated_at = datetime.strptime(collections.data[0].updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")

        total_versions = self.collections_versions_v3api.list(
            "pulp_installer", "pulp", self.base_path
        ).meta["count"]

        self.assertEqual(highest_version, original_highest_version)
        self.assertEqual(original_total_versions, total_versions + 1)
        self.assertGreater(updated_at, original_updated_at)
