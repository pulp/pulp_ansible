"""Tests related to sync ansible plugin collection content type."""
import os
import unittest

from pulpcore.client.pulp_ansible import (
    AnsibleRepositorySyncURL,
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsApi,
    RepositoriesAnsibleApi,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.bindings import PulpTaskError, PulpTestCase

from pulp_ansible.tests.functional.utils import (
    gen_ansible_client,
    gen_ansible_remote,
    monitor_task,
    tasks,
)
from pulp_ansible.tests.functional.utils import SyncHelpersMixin, TestCaseUsingBindings
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncCollectionsFromPulpServerTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """
    Test whether one can sync collections from a Pulp server.

    This performs two sync's, the first uses the V2 API and galaxy.ansible.com. The second is from
    Pulp using the V3 API and uses the content brought in from the first sync.

    """

    def setUp(self):
        """Set up the Sync tests."""
        self.requirements_file = "collections:\n  - testing.k8s_demo_collection"
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=self.requirements_file,
            sync_dependencies=False,
        )
        self.remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, self.remote.pulp_href)

        self.first_repo = self._create_repo_and_sync_with_remote(self.remote)
        self.distribution = self._create_distribution_from_repo(self.first_repo)

    def test_sync_collections_from_pulp(self):
        """Test sync collections from pulp server."""
        second_body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=self.requirements_file,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_and_sync_with_remote(second_remote)

        first_content = self.cv_api.list(
            repository_version=f"{self.first_repo.pulp_href}versions/1/"
        )
        self.assertGreaterEqual(len(first_content.results), 1)
        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(second_content.results), 1)

    def test_sync_collections_from_pulp_using_mirror_second_time(self):
        """Test sync collections from pulp server using a mirror option the second time."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        first_repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(first_repo)

        second_body = gen_ansible_remote(url=distribution.client_url, include_pulp_auth=True)
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_and_sync_with_remote(second_remote)

        first_content = self.cv_api.list(repository_version=f"{first_repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(first_content.results), 1)
        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(second_content.results), 1)

    def test_sync_collection_named_api(self):
        """Test sync collections from pulp server."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - rswaf.api",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        collection = self.collections_v3api.read("api", "rswaf", distribution.base_path)

        self.assertEqual("api", collection.name)
        self.assertEqual("rswaf", collection.namespace)

    def test_noop_resync_collections_from_pulp(self):
        """Test whether sync yields no-op when repo hasn't changed since last sync."""
        second_body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=self.requirements_file,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_with_attached_remote_and_sync(second_remote)

        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(second_content.results), 1)

        # Resync
        repository_sync_data = AnsibleRepositorySyncURL(
            remote=second_remote.pulp_href, optimize=True
        )
        sync_response = self.repo_api.sync(second_repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        second_repo = self.repo_api.read(second_repo.pulp_href)
        task = tasks.read(sync_response.task)

        msg = "no-op: {url} did not change since last sync".format(url=second_remote.url)
        messages = [r.message for r in task.progress_reports]
        self.assertIn(msg, str(messages))

    def test_noop_resync_with_mirror_from_pulp(self):
        """Test whether no-op sync with mirror=True doesn't remove repository content."""
        second_body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=self.requirements_file,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_with_attached_remote_and_sync(second_remote)

        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(second_content.results), 1)

        # Resync
        repository_sync_data = AnsibleRepositorySyncURL(
            remote=second_remote.pulp_href, optimize=True, mirror=True
        )
        sync_response = self.repo_api.sync(second_repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        second_repo = self.repo_api.read(second_repo.pulp_href)
        self.assertEqual(int(second_repo.latest_version_href[-2]), 1)
        task = tasks.read(sync_response.task)

        msg = "no-op: {url} did not change since last sync".format(url=second_remote.url)
        messages = [r.message for r in task.progress_reports]
        self.assertIn(msg, str(messages))

    def test_update_requirements_file(self):
        """Test requirements_file update."""
        body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=self.requirements_file,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_with_attached_remote_and_sync(remote)
        self.assertIsNotNone(repo.last_synced_metadata_time)

        response = self.remote_collection_api.partial_update(
            remote.pulp_href, {"requirements_file": "collections:\n  - ansible.posix"}
        )
        monitor_task(response.task)

        repo = self.repo_api.read(repo.pulp_href)
        self.assertIsNone(repo.last_synced_metadata_time)

    def test_sync_with_missing_collection(self):
        """Test that syncing with a non-present collection gives a useful error."""
        body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file="collections:\n  - absent.not_present",
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        with self.assertRaises(PulpTaskError) as cm:
            self._create_repo_and_sync_with_remote(remote)

        task_result = cm.exception.task.to_dict()
        msg = "absent.not_present does not exist"
        self.assertIn(msg, task_result["error"]["description"], task_result["error"]["description"])


@unittest.skipUnless(
    "AUTOMATION_HUB_TOKEN_AUTH" in os.environ,
    "'AUTOMATION_HUB_TOKEN_AUTH' env var is not defined",
)
class AutomationHubV3SyncCase(PulpTestCase, SyncHelpersMixin):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleApiV3CollectionsApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)
        cls.url = "https://cloud.redhat.com/api/automation-hub/"
        cls.aurl = (
            "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
        )

    def test_sync_with_token_from_automation_hub(self):
        """Test whether we can sync with an auth token from Automation Hub."""
        body = gen_ansible_remote(
            url=self.url,
            requirements_file="collections:\n  - ansible.posix",
            auth_url=self.aurl,
            token=os.environ["AUTOMATION_HUB_TOKEN_AUTH"],
            rate_limit=10,
            tls_validation=False,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Check content of both repos.
        original_content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertTrue(len(original_content.results) >= 3)  # check that we have at least 3 results

    @unittest.skip("Skipping until synclist no longer creates new repository")
    def test_syncing_with_excludes_list_from_automation_hub(self):
        """Test if syncing collections know to be on the synclist will be mirrored."""
        namespace = "autohubtest2"
        # Collections are randomly generated, in case of failure, please change the names below:
        name = "collection_dep_a_zzduuntr"
        excluded = "collection_dep_a_tworzgsx"
        excluded_version = "awcrosby.collection_test==2.1.0"
        requirements = f"""
        collections:
          - {namespace}.{name}
          - {namespace}.{excluded}
          - {excluded_version}
        """
        body = gen_ansible_remote(
            url=self.url,
            requirements_file=requirements,
            auth_url=self.aurl,
            token=os.environ["AUTOMATION_HUB_TOKEN_AUTH"],
            rate_limit=10,
            tls_validation=False,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Assert that at least one CollectionVersion was downloaded
        repo_ver = f"{repo.pulp_href}versions/1/"
        content = self.cv_api.list(repository_version=repo_ver)
        self.assertTrue(content.count >= 1)

        # Assert that excluded collection was not synced
        exclude_content = self.cv_api.list(repository_version=repo_ver, name=excluded)
        self.assertTrue(exclude_content.count == 0)


# TODO QA-AH has been deprecated, remove/replace tests
@unittest.skipUnless(
    "QA_AUTOMATION_HUB_TOKEN_AUTH" in os.environ,
    "'QA_AUTOMATION_HUB_TOKEN_AUTH' env var is not defined",
)
class AutomationHubCIV3SyncCase(PulpTestCase, SyncHelpersMixin):
    """Test syncing from Pulp to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_api = PulpAnsibleApiV3CollectionsApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)
        cls.url = "https://qa.cloud.redhat.com/api/automation-hub/"
        cls.aurl = (
            "https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
        )

    def test_mirror_from_automation_hub_ci_with_auth_token(self):
        """Test whether we can mirror from Automation Hub CI with an auth token."""
        body = gen_ansible_remote(
            url=self.url,
            auth_url=self.aurl,
            token=os.environ["QA_AUTOMATION_HUB_TOKEN_AUTH"],
            rate_limit=10,
            tls_validation=False,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        # Assert at least one hundred CollectionVersions are returned
        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertTrue(len(content.results) >= 100)

    def test_sync_from_automation_hub_ci_with_auth_token_and_requirements_file(self):
        """Test sync from Automation Hub CI with an auth token and requirements file."""
        namespace = "autohubtest2"
        # Collections are randomly generated, in case of failure, please change the name below:
        name = "collection_dep_a_zzduuntr"
        body = gen_ansible_remote(
            url=self.url,
            requirements_file=f"collections:\n  - {namespace}.{name}",
            auth_url=self.aurl,
            token=os.environ["QA_AUTOMATION_HUB_TOKEN_AUTH"],
            rate_limit=10,
            tls_validation=False,
            sync_dependencies=False,
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
            url=self.url,
            auth_url=self.aurl,
            token="invalid token string",
            tls_validation=False,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        with self.assertRaises(PulpTaskError) as cm:
            self._create_repo_and_sync_with_remote(remote)

        task_result = cm.exception.task.to_dict()
        msg = (
            "400, message='Bad Request', url=URL("
            "'https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token')"
        )
        self.assertEqual(
            msg, task_result["error"]["description"], task_result["error"]["description"]
        )
