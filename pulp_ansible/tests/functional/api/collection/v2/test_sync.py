# coding=utf-8
"""Tests related to sync ansible plugin collection content type."""
import unittest
from random import randint
from functools import reduce
from urllib.parse import urlsplit, urljoin

from pulp_smash import api, config
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
    get_added_content_summary,
    get_content,
    get_content_summary,
    get_removed_content_summary,
    sync,
)


from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_CONTENT_NAME,
    ANSIBLE_COLLECTION_FIXTURE_COUNT,
    ANSIBLE_COLLECTION_FIXTURE_URL_V2,
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_COLLECTION_REQUIREMENT,
    ANSIBLE_COLLECTION_TESTING_URL_V2,
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_FIXTURE_CONTENT_SUMMARY,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_REPO_PATH,
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
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        self.assertIsNone(repo["latest_version_href"], repo)
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertIsNotNone(repo["latest_version_href"], repo)

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
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        number_of_syncs = randint(1, 5)
        for _ in range(number_of_syncs):
            sync(self.cfg, remote, repo)

        repo = self.client.get(repo["pulp_href"])
        path = urlsplit(repo["latest_version_href"]).path
        latest_repo_version = int(path.split("/")[-2])
        self.assertEqual(latest_repo_version, 1, repo)

    def test_mirror_sync(self):
        """Sync multiple remotes into the same repo with mirror as `True`.

        This test targets the following issue: 5167

        * `<https://pulp.plan.io/issues/5167>`_

        This test does the following:

        1. Create a repo.
        2. Create two remotes
            a. Role remote
            b. Collection remote
        3. Sync the repo with Role remote.
        4. Sync the repo with Collection remote with ``Mirror=True``.
        5. Verify whether the content in the latest version of the repo
           has only Collection content and Role content is deleted.
        """
        # Step 1
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        # Step 2
        role_remote = self.client.post(ANSIBLE_REMOTE_PATH, gen_ansible_remote())
        self.addCleanup(self.client.delete, role_remote["pulp_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(url=ANSIBLE_COLLECTION_FIXTURE_URL_V2),
        )
        self.addCleanup(self.client.delete, collection_remote["pulp_href"])

        # Step 3
        sync(self.cfg, role_remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertIsNotNone(repo["latest_version_href"])
        self.assertDictEqual(get_added_content_summary(repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

        # Step 4
        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["pulp_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(
            added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

        # Step 5
        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(
            content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )
        self.assertDictEqual(get_removed_content_summary(repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

    def test_mirror_sync_with_requirements(self):
        """
        Sync multiple remotes into the same repo with mirror as `True` using requirements.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_

        This test does the following:

        1. Create a repo.
        2. Create two remotes
            a. Role remote
            b. Collection remote
        3. Sync the repo with Role remote.
        4. Sync the repo with Collection remote with ``Mirror=True``.
        5. Verify whether the content in the latest version of the repo
           has only Collection content and Role content is deleted.
        """
        # Step 1
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        # Step 2
        role_remote = self.client.post(ANSIBLE_REMOTE_PATH, gen_ansible_remote())
        self.addCleanup(self.client.delete, role_remote["pulp_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(
                url=ANSIBLE_COLLECTION_TESTING_URL_V2,
                requirements_file=ANSIBLE_COLLECTION_REQUIREMENT,
            ),
        )

        self.addCleanup(self.client.delete, collection_remote["pulp_href"])

        # Step 3
        sync(self.cfg, role_remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertIsNotNone(repo["latest_version_href"], repo)
        self.assertDictEqual(get_added_content_summary(repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

        # Step 4
        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["pulp_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(
            added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

        # Step 5
        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(
            content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )
        self.assertDictEqual(get_removed_content_summary(repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

    def test_mirror_sync_with_invalid_requirements(self):
        """
        Sync multiple remotes into the same repo with mirror as `True` with invalid requirement.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_

        This test does the following:

        Try to create a Collection remote with invalid requirement
        """
        collection_remote = self.client.using_handler(api.echo_handler).post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(url=ANSIBLE_COLLECTION_FIXTURE_URL_V2, requirements_file="INVALID"),
        )

        self.assertEqual(collection_remote.status_code, 400, collection_remote)


class SyncCollectionsFromPulpServerTestCase(unittest.TestCase):
    """Test whether one can sync collections from a Pulp server.

    This test targets the following issue:

    `Pulp #5333 <https://pulp.plan.io/issues/5333>`_
    """

    def test_sync_collections_from_pulp(self):
        """Test sync collections from pulp server."""
        cfg = config.get_config()
        client = api.Client(cfg)
        repo = client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo["pulp_href"])

        remote = client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2),
        )
        self.addCleanup(client.delete, remote["pulp_href"])

        sync(cfg, remote, repo)
        repo = client.get(repo["pulp_href"])

        distribution = client.post(
            ANSIBLE_DISTRIBUTION_PATH, gen_distribution(repository=repo["pulp_href"])
        )
        self.addCleanup(client.delete, distribution["pulp_href"])

        second_repo = client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, second_repo["pulp_href"])

        url = reduce(
            urljoin,
            (
                cfg.get_base_url(),
                "pulp_ansible/galaxy/",
                distribution["base_path"] + "/",
                "api/v2/collections",
            ),
        )

        pulp_remote = client.post(ANSIBLE_COLLECTION_REMOTE_PATH, gen_ansible_remote(url=url))
        self.addCleanup(client.delete, pulp_remote["pulp_href"])

        sync(cfg, pulp_remote, second_repo)
        second_repo = client.get(second_repo["pulp_href"])

        self.assertEqual(get_content(repo), get_content(second_repo))
