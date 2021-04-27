"""Tests collection sync using the Galaxy V2 API."""
import os
import unittest

from pulpcore.client.pulp_ansible import ApiException

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


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

    @unittest.skipUnless(
        "MIRROR_GALAXY" in os.environ,
        "'MIRROR_GALAXY' env var is not defined",
    )
    def test_mirror_galaxy(self):
        """Mirror Galaxy."""
        body = gen_ansible_remote(url="https://galaxy.ansible.com")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(remote)

        content = self.cv_api.list(repository_version=f"{repo.pulp_href}versions/1/")
        self.assertGreaterEqual(len(content.results), 300)


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
