# coding=utf-8
"""Tests that content hosted by Pulp can be consumed by ansible-galaxy."""
from os import path
import tempfile
import unittest

from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp3.utils import gen_distribution, gen_repo, sync

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_COLLECTION_TESTING_URL_V2,
    ANSIBLE_REPO_PATH,
    COLLECTION_WHITELIST,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ConsumeContentTestCase(unittest.TestCase):
    """Test whether ansible-galaxy can install content hosted by Pulp.

    This test targets the following issue:

    `Pulp #4915 <https://pulp.plan.io/issues/4915>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)
        cls.cli_client = cli.Client(cls.cfg, local=True)
        try:
            cls.cli_client.run(["which", "ansible-galaxy"])
        except exceptions.CalledProcessError:
            raise unittest.SkipTest("This test requires ansible-galaxy client.")

    def test_consume_content(self):
        """Test whether ansible-galaxy can install content hosted by Pulp."""
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        self.assertIsNone(repo["latest_version_href"])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])

        # Create distribution
        distribution = self.client.post(
            ANSIBLE_DISTRIBUTION_PATH, gen_distribution(repository=repo["pulp_href"])
        )
        self.addCleanup(self.client.delete, distribution["pulp_href"])

        with tempfile.TemporaryDirectory() as temp_dir:
            self.cli_client.run(
                "ansible-galaxy collection install {} -c -s {} -p {}".format(
                    COLLECTION_WHITELIST, distribution["client_url"], temp_dir
                ).split()
            )

            directory = "{}/ansible_collections/{}".format(
                temp_dir, COLLECTION_WHITELIST.replace(".", "/")
            )
            self.assertTrue(path.exists(directory), "Could not find directory {}".format(directory))
