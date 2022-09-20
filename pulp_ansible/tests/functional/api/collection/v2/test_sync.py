"""Tests collection sync using the Galaxy V2 API."""
import pytest
from pulpcore.client.pulp_ansible import ApiException

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_smash.pulp3.bindings import monitor_task


class SyncTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Galaxy V2 Collection sync tests."""

    def test_sync_simple_collections_file(self):
        """Sync with simple requirements file, expected to download one CollectionVersion."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertEqual(len(content.results), 1)

    def test_sync_with_slash(self):
        """Sync with a slash used in remote.url, expected to download one CollectionVersion."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com/",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertEqual(len(content.results), 1)

    def test_sync_with_specific_version(self):
        """Sync with simple requirements file, expected to download one CollectionVersion."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: arista.avd\n    version: 2.0.0",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        versions = self.collections_versions_v3api.list("avd", "arista", distribution.base_path)

        self.assertEqual(versions.meta.count, 1)

    def test_sync_all_versions(self):
        """Sync with simple requirements file, expected to download CollectionVersion."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: arista.avd",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)
        distribution = self._create_distribution_from_repo(repo)

        versions = self.collections_versions_v3api.list("avd", "arista", distribution.base_path)

        self.assertGreater(versions.meta.count, 1)

    def test_sync_with_attached_remote(self):
        """Sync with a CollectionRemote attached to the repository."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_with_attached_remote_and_sync(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertEqual(len(content.results), 1)

    def test_successive_syncs_repo_version(self):
        """Test whether successive syncs do not produce more repository versions."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_with_attached_remote_and_sync(remote)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}1/")
        repo = self._sync_repo(repo)
        self.assertEqual(repo.latest_version_href, f"{repo.versions_href}1/")

    def test_sync_with_multiple_versions_pages(self):
        """Sync with requirements.yml that requires parsing multiple "versions" pages."""
        requirements_file_string = "\n" "---\n" "collections:\n" "- name: amazon.aws\n"
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements_file_string,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 1)

    def test_sync_with_invalid_requirements(self):
        """Sync with invalid requirement."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="INAVLID",
            sync_dependencies=False,
        )
        self.assertRaises(ApiException, self.remote_collection_api.create, body)

    def test_sync_collection_missing_requires_ansible(self):
        """Sync a collection with the expected `requires_ansible` data missing."""
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: inexio.thola\n    version: 1.0.0",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 1)

    @pytest.mark.nightly
    def test_mirror_galaxy(self):
        """Mirror Galaxy."""
        body = gen_ansible_remote(url="https://galaxy.ansible.com")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(content.count, 300)


class RequirementsFileVersionsTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Galaxy V2 Collection sync tests for version restriction."""

    def test_sync_with_version_equality(self):
        """Sync using a requirements.yml with an equality specifier."""
        requirements_file_string = (
            "\n"
            "---\n"
            "collections:\n"
            "- name: robertdebock.ansible_development_environment\n"
            '  version: "==1.0.1"\n'
        )
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements_file_string,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 1)

    def test_sync_with_two_equality_entries_on_different_lines(self):
        """Sync using a requirements.yml with the same collection used on two lines."""
        requirements_file_string = (
            "\n"
            "---\n"
            "collections:\n"
            "- name: robertdebock.ansible_development_environment\n"
            '  version: "1.0.1"\n'
            "- name: robertdebock.ansible_development_environment\n"
            '  version: "1.0.0"\n'
        )
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements_file_string,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 2)

    def test_sync_with_one_version_inequality(self):
        """Sync using a requirements.yml with one version inequality."""
        requirements_file_string = (
            "\n"
            "---\n"
            "collections:\n"
            "- name: robertdebock.ansible_development_environment\n"
            '  version: ">=1.0.1"\n'
        )
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements_file_string,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 2)

    def test_sync_with_two_version_inequalities(self):
        """Sync using a requirements.yml with two version inequalities."""
        requirements_file_string = (
            "\n"
            "---\n"
            "collections:\n"
            "- name: robertdebock.ansible_development_environment\n"
            '  version: ">1.0.0,<1.0.2"\n'
        )
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements_file_string,
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 1)

    def test_sync_and_rebuild(self):
        """Sync with simple requirements file, expected to download one CollectionVersion."""
        # /pulp/api/v3/repositories/ansible/ansible/<pk>/rebuild_metadata/
        #    pulp_ansible.app.viewsets.AnsibleRepositoryViewSet
        #    repositories-ansible/ansible-rebuild-metadata
        # /pulp/api/v3/repositories/ansible/ansible/<pk>/rebuild_metadata\.<format>/
        #     pulp_ansible.app.viewsets.AnsibleRepositoryViewSet
        #     repositories-ansible/ansible-rebuild-metadata

        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: community.docker\n    version: 3.0.0",
            sync_dependencies=False,
        )
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # this will make the repo and sync the collection from upstream into it
        # when the builtin repo cleanup is called, the collection will be
        # orphaned and testcaseusebindings will delete it via orphan_cleanup
        # in the teardown method
        repo = self._create_repo_and_sync_with_remote(remote)

        # get the before data
        before = self.cv_api.list(repository_version=repo.latest_version_href)
        before = before.results[0].to_dict()
        assert before["docs_blob"] == {}

        # pass in the namespace/name/version just to verify kwargs are allowed
        rebuild_task = self.repo_api.rebuild_metadata(
            repo.pulp_href, {"namespace": "community", "name": "docker", "version": "3.0.0"}
        )
        res = monitor_task(rebuild_task.task)
        assert res.state == "completed"

        # get the after data
        after = self.cv_api.list(repository_version=repo.latest_version_href)
        after = after.results[0].to_dict()

        assert after["docs_blob"]["collection_readme"]["name"] == "README.md"
        assert (
            "<h1>Docker Community Collection</h1>"
            in after["docs_blob"]["collection_readme"]["html"]
        )
