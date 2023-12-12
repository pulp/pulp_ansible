"""Tests related to sync ansible plugin collection content type."""

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL

from pulpcore.tests.functional.utils import PulpTaskError

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    monitor_task,
)
from pulp_ansible.tests.functional.utils import TestCaseUsingBindings

REQUIREMENTS_FILE = "collections:\n  - testing.k8s_demo_collection"


class SyncCollectionsFromPulpServerTestCase(TestCaseUsingBindings):
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
            requirements_file=REQUIREMENTS_FILE,
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
            requirements_file=REQUIREMENTS_FILE,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_and_sync_with_remote(second_remote)

        first_content = self.cv_api.list(
            repository_version=f"{self.first_repo.pulp_href}versions/1/"
        )
        assert len(first_content.results) >= 1
        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        assert len(second_content.results) >= 1

    def test_sync_collections_from_pulp_using_mirror_second_time(self):
        """Test sync collections from pulp server using a mirror option the second time."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=REQUIREMENTS_FILE,
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
        assert len(first_content.results) >= 1
        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        assert len(second_content.results) >= 1

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

        assert "api" == collection.name
        assert "rswaf" == collection.namespace

    def test_noop_resync_collections_from_pulp(self):
        """Test whether sync yields no-op when repo hasn't changed since last sync."""
        second_body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=REQUIREMENTS_FILE,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_with_attached_remote_and_sync(second_remote)

        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        assert len(second_content.results) >= 1

        # Resync
        repository_sync_data = AnsibleRepositorySyncURL(
            remote=second_remote.pulp_href, optimize=True
        )
        sync_response = self.repo_api.sync(second_repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)
        second_repo = self.repo_api.read(second_repo.pulp_href)

        msg = "no-op: {url} did not change since last sync".format(url=second_remote.url)
        messages = [r.message for r in task.progress_reports]
        assert msg in str(messages)

    def test_noop_resync_with_mirror_from_pulp(self):
        """Test whether no-op sync with mirror=True doesn't remove repository content."""
        second_body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=REQUIREMENTS_FILE,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(second_body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_with_attached_remote_and_sync(second_remote)

        second_content = self.cv_api.list(repository_version=f"{second_repo.pulp_href}versions/1/")
        assert len(second_content.results) >= 1

        # Resync
        repository_sync_data = AnsibleRepositorySyncURL(
            remote=second_remote.pulp_href, optimize=True, mirror=True
        )
        sync_response = self.repo_api.sync(second_repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)
        second_repo = self.repo_api.read(second_repo.pulp_href)
        assert int(second_repo.latest_version_href[-2]) == 1

        msg = "no-op: {url} did not change since last sync".format(url=second_remote.url)
        messages = [r.message for r in task.progress_reports]
        assert msg in str(messages)

    def test_update_requirements_file(self):
        """Test requirements_file update."""
        body = gen_ansible_remote(
            url=self.distribution.client_url,
            requirements_file=REQUIREMENTS_FILE,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_with_attached_remote_and_sync(remote)
        assert repo.last_synced_metadata_time is not None

        response = self.remote_collection_api.partial_update(
            remote.pulp_href, {"requirements_file": "collections:\n  - ansible.posix"}
        )
        monitor_task(response.task)

        repo = self.repo_api.read(repo.pulp_href)
        assert repo.last_synced_metadata_time is None

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
        assert msg in task_result["error"]["description"], task_result["error"]["description"]
