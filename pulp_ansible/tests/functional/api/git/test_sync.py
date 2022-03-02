"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""
from os import path
import subprocess
import tempfile

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_distribution

from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class GitRemoteSyncInstallTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Collection sync tests for collections with unique properties."""

    def test_sync_collection_from_git(self):
        """Sync collections from Git repositories and then install one of them."""
        body = gen_ansible_remote(url="https://github.com/pulp/pulp_installer.git")
        installer_remote = self.remote_git_api.create(body)
        self.addCleanup(self.remote_git_api.delete, installer_remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(installer_remote)

        content = self.cv_api.list(repository_version=repo.latest_version_href)
        self.assertEqual(len(content.results), 1)

        repo = self._sync_repo(repo, remote=installer_remote.pulp_href)

        content = self.cv_api.list(repository_version=repo.latest_version_href)
        self.assertEqual(len(content.results), 1)

        body = gen_ansible_remote(url="https://github.com/pulp/squeezer.git")

        squeezer_remote = self.remote_git_api.create(body)
        self.addCleanup(self.remote_git_api.delete, squeezer_remote.pulp_href)

        repo = self._sync_repo(repo, remote=squeezer_remote.pulp_href)

        content = self.cv_api.list(repository_version=repo.latest_version_href)
        self.assertEqual(len(content.results), 2)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)
        collection_name = "pulp.squeezer"
        with tempfile.TemporaryDirectory() as temp_dir:

            # The install command needs --pre so a pre-release collection versions install
            cmd = "ansible-galaxy collection install --pre {} -c -s {} -p {}".format(
                collection_name, distribution.client_url, temp_dir
            )

            directory = "{}/ansible_collections/{}".format(
                temp_dir, collection_name.replace(".", "/")
            )

            self.assertTrue(
                not path.exists(directory), "Directory {} already exists".format(directory)
            )

            subprocess.run(cmd.split())

            self.assertTrue(path.exists(directory), "Could not find directory {}".format(directory))

    def test_sync_metadata_only_collection_from_git(self):
        """Sync collections from Git repositories with metadata_only=True."""
        body = gen_ansible_remote(
            url="https://github.com/ansible-collections/amazon.aws/",
            metadata_only=True,
            git_ref="2.1.0",
        )
        amazon_remote = self.remote_git_api.create(body)
        self.addCleanup(self.remote_git_api.delete, amazon_remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(amazon_remote)

        content = self.cv_api.list(repository_version=repo.latest_version_href)
        self.assertEqual(len(content.results), 1)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        version = self.collections_versions_v3api.read(
            "aws", "amazon", distribution.base_path, "2.1.0"
        )

        self.assertEqual(version.git_url, "https://github.com/ansible-collections/amazon.aws/")
        self.assertEqual(version.git_commit_sha, "013162a952c7b2d11c7e2ebf443d8d4d7a21e95a")
        self.assertEqual(version.download_url, None)

    def test_sync_collection_from_git_commit_sha(self):
        """Sync collections from Git repositories with git_ref that is a commit sha."""
        body = gen_ansible_remote(
            url="https://github.com/ansible-collections/amazon.aws/",
            metadata_only=True,
            git_ref="d0b54fc082cb63f63d34246c8fe668e19e74777c",
        )
        amazon_remote = self.remote_git_api.create(body)
        self.addCleanup(self.remote_git_api.delete, amazon_remote.pulp_href)

        repo = self._create_repo_and_sync_with_remote(amazon_remote)

        content = self.cv_api.list(repository_version=repo.latest_version_href)
        self.assertEqual(len(content.results), 1)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        version = self.collections_versions_v3api.read(
            "aws", "amazon", distribution.base_path, "1.5.1"
        )

        self.assertEqual(version.git_url, "https://github.com/ansible-collections/amazon.aws/")
        self.assertEqual(version.git_commit_sha, "d0b54fc082cb63f63d34246c8fe668e19e74777c")
        self.assertEqual(version.download_url, None)

    def test_sync_metadata_only_collection_from_pulp(self):
        """Sync collections from another Pulp that only has metadata.

        Create a GitRemote
        Create a repository
        Sync from the remote
        Create distribution to serve the repository
        Create CollectionRemote pointing to the distribution.
        Create a second repository.
        Sync using the CollectionRemote into the second repository.
        Assert content is added to the second repository.

        """
        body = gen_ansible_remote(
            url="https://github.com/ansible-collections/amazon.aws/",
            metadata_only=True,
            git_ref="2.1.0",
        )
        amazon_remote = self.remote_git_api.create(body)
        self.addCleanup(self.remote_git_api.delete, amazon_remote.pulp_href)

        self.first_repo = self._create_repo_and_sync_with_remote(amazon_remote)

        content = self.cv_api.list(repository_version=self.first_repo.latest_version_href)
        self.assertEqual(len(content.results), 1)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = self.first_repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        self.distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, self.distribution.pulp_href)

        self.requirements_file = "collections:\n  - amazon.aws"

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
