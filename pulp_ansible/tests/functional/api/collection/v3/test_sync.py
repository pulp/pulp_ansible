# coding=utf-8
"""Tests related to sync ansible plugin collection content type."""
import unittest

from pulpcore.client.pulp_ansible import (
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    RepositorySyncURL,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_TESTING_URL_V2,
    ANSIBLE_DEMO_COLLECTION,
)
from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote, monitor_task
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class PulpToPulpSyncCase(unittest.TestCase):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)

    def test_v3_sync(self):
        """Test syncing Pulp to Pulp over v3 api."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/1/")

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        distribution_url = monitor_task(distribution_create.task)
        distribution = self.distributions_api.read(distribution_url[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        # Create a second repo.
        mirror_repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, mirror_repo.pulp_href)

        url = (
            distribution.client_url
            + "/api/v3/collections/"
            + ANSIBLE_DEMO_COLLECTION.replace(".", "/")
        )
        body = gen_ansible_remote(url=url)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # Sync the second repository.
        self.assertEqual(mirror_repo.latest_version_href, f"{mirror_repo.pulp_href}versions/0/")
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(mirror_repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        mirror_repo = self.repo_api.read(mirror_repo.pulp_href)
        self.assertEqual(mirror_repo.latest_version_href, f"{mirror_repo.pulp_href}versions/1/")

        # Check content of both repos.
        original_content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        mirror_content = self.cv_api.list(repository_version=f"{mirror_repo.pulp_href}versions/1/")
        self.assertTrue(mirror_content.results)  # check that we have some results
        self.assertEqual(sorted(original_content.results), sorted(mirror_content.results))
