"""Tests related to Galaxy V3 serializers."""
import unittest

from pulpcore.client.pulp_ansible import (
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


class DeprecationTestCase(unittest.TestCase):
    """Test deprecation status sync."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleGalaxyApiCollectionsApi(cls.client)
        cls.collections_versions_v3api = PulpAnsibleGalaxyApiV3VersionsApi(cls.client)

    def setUp(self):
        """Create distribution for V3."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.repo_href = repo.pulp_href
        requirements = (
            "collections:\n  - name: testing.k8s_demo_collection\n  - name: pulp.pulp_installer"
        )

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
        self.client_url = distribution.client_url
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

    def test_v3_deprecation(self):
        """Test deprecation status sync."""
        collections = self.collections_api.list(self.base_path, namespace="testing")
        self.collections_api.update(
            "k8s_demo_collection", "testing", self.base_path, {"deprecated": True}
        )

        self.assertTrue(collections.data[0].deprecated)

        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.repo_href = repo.pulp_href
        requirements = "collections:\n  - name: testing.k8s_demo_collection"

        body = gen_ansible_remote(url=self.client_url, requirements_file=requirements)
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
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        collections = self.collections_api.list(distribution.base_path, namespace="testing")

        self.assertTrue(collections.data[0].deprecated)

        self.collections_api.update(
            "k8s_demo_collection", "testing", self.base_path, {"deprecated": False}
        )

        requirements = (
            "collections:\n  - name: testing.k8s_demo_collection\n  - name: pulp.pulp_installer"
        )

        self.remote_collection_api.partial_update(
            remote.pulp_href, {"requirements_file": requirements}
        )

        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)

        collections = self.collections_api.list(distribution.base_path)
        for collection in collections.data:
            self.assertFalse(collection.deprecated)
