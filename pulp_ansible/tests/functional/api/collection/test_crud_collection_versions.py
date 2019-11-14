# coding=utf-8
"""Tests related to sync ansible plugin collection content type."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync


from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_COLLECTION_TESTING_URL_V2,
    ANSIBLE_COLLECTION_VERSION_CONTENT_PATH,
    ANSIBLE_REPO_PATH,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ListContentVersionsCase(unittest.TestCase):
    """Test listing CollectionVersions."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)

    def test_tags_filter(self):
        """Filter CollectionVersions by using the tags filter.

        This test targets the following issue:

        * `Pulp #5571 <https://pulp.plan.io/issues/5571>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the remote.
        3. Attempt to filter the CollectionVersions by different tags

        Note that the testing.k8s_demo_collection collection has tags 'k8s' and 'kubernetes'.
        """
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        sync(self.cfg, remote, repo)

        # filter collection versions by tags
        params = {"tags": "nada"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 0, collections)

        params = {"tags": "k8s"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 1, collections)

        params = {"tags": "k8s,kubernetes"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 1, collections)

        params = {"tags": "nada,k8s"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 0, collections)
