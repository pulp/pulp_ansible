"""Tests that Roles hosted by Pulp can be installed by ansible-galaxy."""

from os import path
import subprocess
import tempfile
import unittest

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    RepositorySyncURL,
    RemotesRoleApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_ELASTIC_FIXTURE_URL,
    ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME,
    ANSIBLE_ELASTIC_ROLE,
)
from pulp_ansible.tests.functional.utils import (
    gen_ansible_client,
    gen_ansible_remote,
    monitor_task,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class InstallRoleTestCase(unittest.TestCase):
    """Test whether ansible-galaxy can install a Role hosted by Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_role_api = RemotesRoleApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)

    def test_install_role(self):
        """Test whether ansible-galaxy can install a Role hosted by Pulp."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_ansible_remote(url=ANSIBLE_ELASTIC_FIXTURE_URL)
        remote = self.remote_role_api.create(body)
        self.addCleanup(self.remote_role_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
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

        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = "ansible-galaxy role install {} -c -s {} -p {}".format(
                ANSIBLE_ELASTIC_ROLE, distribution.client_url, temp_dir
            )

            directory = "{}/{}".format(temp_dir, ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME)

            self.assertTrue(
                not path.exists(directory), "Directory {} already exists".format(directory)
            )

            subprocess.run(cmd.split())

            self.assertTrue(path.exists(directory), "Could not find directory {}".format(directory))
