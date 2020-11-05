"""Tests related to sync ansible plugin collection content type."""
import os
import unittest

import pytest

from pulpcore.client.pulp_ansible import (
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleGalaxyApiCollectionsApi,
    RepositoriesAnsibleApi,
    RepositorySyncURL,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import SyncHelpersMixin
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

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
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

        body = gen_ansible_remote(url=distribution.client_url, requirements_file=DEMO_REQUIREMENTS)
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


class BasicSyncCase(unittest.TestCase):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleGalaxyApiCollectionsApi(cls.client)

    @pytest.mark.skip("Skip until we can filter by version: https://pulp.plan.io/issues/7739")
    def test_v3_sync(self):
        """Test syncing Pulp to Pulp over v3 api."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        requirements = 'collections:\n  - source: pulp.pulp_installer\n    version: "<=3.6.2"'

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=requirements)
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
        original_path = distribution.base_path

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        # Create a second repo.
        mirror_repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, mirror_repo.pulp_href)

        COLLECTION_VERSION = "3.6.2"
        body = gen_ansible_remote(url=distribution.client_url, requirements_file=requirements)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # Sync the second repository.
        self.assertEqual(mirror_repo.latest_version_href, f"{mirror_repo.pulp_href}versions/0/")
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(mirror_repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        mirror_repo = self.repo_api.read(mirror_repo.pulp_href)
        self.assertEqual(mirror_repo.latest_version_href, f"{mirror_repo.pulp_href}versions/1/")

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = mirror_repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        distribution_url = monitor_task(distribution_create.task)
        distribution = self.distributions_api.read(distribution_url[0])
        mirror_path = distribution.base_path

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        # Check content of both repos.
        original_content = self.collections_api.list(path=original_path)
        mirror_content = self.collections_api.list(path=mirror_path)

        self.assertEqual(mirror_content.data[0].highest_version["version"], COLLECTION_VERSION)
        self.assertNotEqual(
            original_content.data[0].highest_version["version"],
            COLLECTION_VERSION,
        )


@unittest.skipUnless(
    "AUTOMATION_HUB_TOKEN_AUTH" in os.environ,
    "'AUTOMATION_HUB_TOKEN_AUTH' env var is not defined",
)
class AutomationHubV3SyncCase(unittest.TestCase, SyncHelpersMixin):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleGalaxyApiCollectionsApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)

    def test_sync_with_token_from_automation_hub(self):
        """Test whether we can sync with an auth token from Automation Hub."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        aurl = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
        body = gen_ansible_remote(
            url="https://cloud.redhat.com/api/automation-hub/",
            requirements_file="collections:\n  - ansible.posix",
            auth_url=aurl,
            token=os.environ["AUTOMATION_HUB_TOKEN_AUTH"],
            tls_validation=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Check content of both repos.
        original_content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertTrue(len(original_content.results) >= 3)  # check that we have at least 3 results


@unittest.skipUnless(
    "CI_AUTOMATION_HUB_TOKEN_AUTH" in os.environ,
    "'CI_AUTOMATION_HUB_TOKEN_AUTH' env var is not defined",
)
class AutomationHubCIV3SyncCase(unittest.TestCase, SyncHelpersMixin):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleGalaxyApiCollectionsApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)
        cls.aurl = (
            "https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
        )

    def test_mirror_from_automation_hub_ci_with_auth_token(self):
        """Test whether we can mirror from Automation Hub CI with an auth token."""
        body = gen_ansible_remote(
            url="https://ci.cloud.redhat.com/api/automation-hub/content/synctest/",
            auth_url=self.aurl,
            token=os.environ["CI_AUTOMATION_HUB_TOKEN_AUTH"],
            tls_validation=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Assert at least one hundred CollectionVersions are returned
        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertTrue(len(content.results) >= 100)

    def test_sync_from_automation_hub_ci_with_auth_token_and_requirements_file(self):
        """Test sync from Automation Hub CI with an auth token and requirements file."""
        name = "collection_dep_a_fdqqyxou"
        namespace = "autohubtest2"
        body = gen_ansible_remote(
            url="https://ci.cloud.redhat.com/api/automation-hub/",
            requirements_file=f"collections:\n  - {namespace}.{name}",
            auth_url=self.aurl,
            token=os.environ["CI_AUTOMATION_HUB_TOKEN_AUTH"],
            tls_validation=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Assert that at least one CollectionVersion was downloaded
        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertTrue(len(content.results) >= 1)

    def test_install_collection_with_invalid_token_from_automation_hub_ci(self):
        """Test whether we can mirror from Automation Hub CI with an invalid auth token."""
        body = gen_ansible_remote(
            url="https://ci.cloud.redhat.com/api/automation-hub/content/synctest/",
            auth_url=self.aurl,
            token="invalid token string",
            tls_validation=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Assert that the sync did not produce a new repository version
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
