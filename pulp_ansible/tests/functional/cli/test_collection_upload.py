"""Tests that Collections can be uploaded to  Pulp with the ansible-galaxy CLI."""

import random
import string
import subprocess
import tempfile
import unittest

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    RemotesCollectionApi,
    RepositoriesAnsibleApi,
    RepositoriesAnsibleVersionsApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.utils import (
    gen_ansible_client,
    monitor_task,
    wait_tasks,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class InstallCollectionTestCase(unittest.TestCase):
    """Test whether ansible-galaxy can upload a Collection to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.repo_versions_api = RepositoriesAnsibleVersionsApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)

    def test_upload_collection(self):
        """Test whether ansible-galaxy can upload a Collection to Pulp."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        distribution_url = monitor_task(distribution_create.task)
        distribution = self.distributions_api.read(distribution_url[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        with tempfile.TemporaryDirectory() as temp_dir:
            collection_name = "".join([random.choice(string.ascii_lowercase) for i in range(26)])
            cmd = "ansible-galaxy collection init --init-path {} pulp.{}".format(
                temp_dir, collection_name
            )
            subprocess.run(cmd.split())

            cmd = "ansible-galaxy collection build --output-path {} {}{}".format(
                temp_dir, temp_dir, "/pulp/" + collection_name + "/"
            )
            subprocess.run(cmd.split())

            repo_version = self.repo_versions_api.read(repo.latest_version_href)
            self.assertEqual(repo_version.number, 0)  # We uploaded 1 collection

            cmd = "ansible-galaxy collection publish -c -s {} {}{}".format(
                distribution.client_url, temp_dir, "/pulp-" + collection_name + "-1.0.0.tar.gz"
            )
            subprocess.run(cmd.split())
            wait_tasks()

        repo = self.repo_api.read(repo.pulp_href)
        repo_version = self.repo_versions_api.read(repo.latest_version_href)
        self.assertEqual(repo_version.number, 1)  # We uploaded 1 collection
