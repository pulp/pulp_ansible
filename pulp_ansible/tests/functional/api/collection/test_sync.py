# coding=utf-8
"""Tests that sync ansible plugin repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    sync,
)

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_GALAXY_COLLECTION_URL,
    COLLECTION_WHITELIST,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicSyncTestCase(unittest.TestCase):
    """Sync repositories with the ansible plugin collections content type.

    This test targets the following issue:

    * `Pulp #4913 <https://pulp.plan.io/issues/4913>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)

    def test_sync(self):
        """Sync repositories with the ansible plugin.

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
           in the repo.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        body = gen_ansible_remote(
            url=ANSIBLE_GALAXY_COLLECTION_URL,
            whitelist=COLLECTION_WHITELIST
        )
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'], repo)
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])
        self.assertIsNotNone(repo['_latest_version_href'], repo)
