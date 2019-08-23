# coding=utf-8
"""Tests that content hosted by Pulp can be consumed by mazer."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import gen_distribution, gen_repo, sync

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_COLLECTION_TESTING_URL,
    COLLECTION_WHITELIST,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ConsumeCotentTestCase(unittest.TestCase):
    """Test whether a client can install collections content hosted by Pulp.

    This test targets the following issues:

    * `Pulp #4915 <https://pulp.plan.io/issues/4915>`_
    * `Pulp #5335 <https://pulp.plan.io/issues/5335>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)
        cls.cli_client = cli.Client(cls.cfg, local=True)
        # TODO pip install git+https://github.com/ansible/ansible.git@devel
        try:
            cls.cli_client.run(["which", "ansible-galaxy"])
        except exceptions.CalledProcessError:
            raise unittest.SkipTest("This test requires ansible-galaxy.")

    def test_consume_content(self):
        """Test whether mazer can install content hosted by Pulp."""
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        # Sync the repository.
        self.assertIsNone(repo["_latest_version_href"])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["_href"])

        # Create distribution
        distribution = self.client.post(
            ANSIBLE_DISTRIBUTION_PATH, gen_distribution(
                repository=repo["_href"])
        )
        self.addCleanup(self.client.delete, distribution["_href"])

        cmd = "ansible-galaxy -vvv collection install {} -p {} -s {}".format(
            COLLECTION_WHITELIST, "~/.ansible/collections/", distribution['mazer_url']).split()
        self.cli_client.run(cmd)

        # self.addCleanup(self.cli_client.run, "mazer remove {}".format(
        #     COLLECTION_WHITELIST).split())

        # response = self.cli_client.run(["mazer", "list"])
        # self.assertIn(COLLECTION_WHITELIST, response.stdout, response)
