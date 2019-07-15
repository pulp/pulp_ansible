# coding=utf-8
"""Tests related to sync ansible plugin collection content type."""
import unittest
from random import randint
from urllib.parse import urlsplit

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import gen_repo, sync

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_GALAXY_COLLECTION_URL,
    COLLECTION_WHITELIST,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncTestCase(unittest.TestCase):
    """Sync the ansible plugin collections content type."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)

    def test_sync(self):
        """Sync repository with the ansible plugin collections content type.

        This test targets the following issue:

        * `Pulp #4913 <https://pulp.plan.io/issues/4913>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_GALAXY_COLLECTION_URL, whitelist=COLLECTION_WHITELIST)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        # Sync the repository.
        self.assertIsNone(repo["_latest_version_href"], repo)
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["_href"])
        self.assertIsNotNone(repo["_latest_version_href"], repo)

    def test_successive_syncs_repo_version(self):
        """Test whether successive syncs update repository versions.

        This test targets the following issue:

        * `Pulp #5000 <https://pulp.plan.io/issues/5000>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the repository an arbitrary number of times.
        3. Verify that the repository version is equal to the previous number
           of syncs.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_GALAXY_COLLECTION_URL, whitelist=COLLECTION_WHITELIST)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        number_of_syncs = randint(1, 5)
        for _ in range(number_of_syncs):
            sync(self.cfg, remote, repo)

        repo = self.client.get(repo["_href"])
        path = urlsplit(repo["_latest_version_href"]).path
        latest_repo_version = int(path.split("/")[-2])
        self.assertEqual(latest_repo_version, number_of_syncs, repo)
