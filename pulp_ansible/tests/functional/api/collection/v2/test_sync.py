"""Tests related to sync ansible plugin collection content type."""
import unittest
from random import randint
from urllib.parse import urlsplit, urljoin

from requests.exceptions import HTTPError

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
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    ANSIBLE_COLLECTION_FIXTURE_COUNT,
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_COLLECTION_REQUIREMENT,
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_FIXTURE_CONTENT_SUMMARY,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_REPO_PATH,
    GALAXY_ANSIBLE_BASE_URL,
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

    def test_remote_urls(self):
        """This tests that the remote url ends with a "/".

        This test targets https://pulp.plan.io/issues/7767

        ansible-galaxy requires a trailing slash: https://git.io/JTMAA

        It does make an exception for "https://galaxy.ansible.com": https://git.io/JTMpk
        """
        body = gen_ansible_remote(url="http://galaxy.ansible.com/api")
        with self.assertRaises(HTTPError) as exc:
            self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.assertEqual(exc.exception.response.status_code, 400)

        body = gen_ansible_remote(url="http://galaxy.example.com")
        with self.assertRaises(HTTPError) as exc:
            self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.assertEqual(exc.exception.response.status_code, 400)

        body = gen_ansible_remote(url="https://galaxy.ansible.com")
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        body = gen_ansible_remote(url="https://galaxy.ansible.com/")
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

    def test_sync(self):
        """Sync repository with the ansible plugin collections content type.

        This test targets the following issue:

        * `Pulp #4913 <https://pulp.plan.io/issues/4913>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is 0.
        3. Sync the remote.
        4. Assert that repository version is 1.
        """
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/0/")
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/1/")

    def test_sync_with_slash(self):
        """Sync repository against a url with a slash at the end."""
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(
            url=f"{GALAXY_ANSIBLE_BASE_URL}/", requirements_file=DEMO_REQUIREMENTS
        )
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/0/")
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/1/")

    def test_sync_with_attached_remote(self):
        """Sync repository with a collection remote on the repository.

        Do the following:

        1. Create a repository, and a remote.
        2. Attach the remote to the repository.
        3. Sync the remote.
        4. Assert that repository version is 1.
        """
        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo(remote=remote["pulp_href"]))
        self.addCleanup(self.client.delete, repo["pulp_href"])

        # Sync the repository.
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])
        self.assertEqual(repo["latest_version_href"], f"{repo['pulp_href']}versions/1/")

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

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
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
            gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS),
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

    def test_sync_with_requirements(self):
        """
        Sync using a complex requirements.yml file.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_
        """
        # Step 1
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(
                url=GALAXY_ANSIBLE_BASE_URL,
                requirements_file=ANSIBLE_COLLECTION_REQUIREMENT,
            ),
        )

        self.addCleanup(self.client.delete, collection_remote["pulp_href"])

        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["pulp_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(
            added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(
            content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

    def test_sync_with_invalid_requirements(self):
        """
        Sync with invalid requirement.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_

        This test does the following:

        Try to create a Collection remote with invalid requirement
        """
        collection_remote = self.client.using_handler(api.echo_handler).post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file="INVALID"),
        )

        self.assertEqual(collection_remote.status_code, 400, collection_remote)

        requirements = "collections:\n  - name: test.test\n    source: http://example.com"
        collection_remote = self.client.using_handler(api.echo_handler).post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=requirements),
        )

        self.assertEqual(collection_remote.status_code, 400, collection_remote)

    def test_sync_with_aws_requirements(self):
        """Test to sync down amazon.aws versions."""
        requirements_file = "collections:\n  - amazon.aws"

        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(
                url=GALAXY_ANSIBLE_BASE_URL,
                requirements_file=requirements_file,
            ),
        )

        self.addCleanup(self.client.delete, collection_remote["pulp_href"])

        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["pulp_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], 67)

        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], 67)


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
            gen_ansible_remote(
                url=GALAXY_ANSIBLE_BASE_URL,
                requirements_file=DEMO_REQUIREMENTS,
            ),
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

        url = distribution["client_url"]
        body = gen_ansible_remote(url=url, requirements_file=DEMO_REQUIREMENTS)
        pulp_remote = client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(client.delete, pulp_remote["pulp_href"])

        sync(cfg, pulp_remote, second_repo)
        second_repo = client.get(second_repo["pulp_href"])

        self.assertEqual(get_content(repo), get_content(second_repo))

        galaxy_collection_data = client.get(
            urljoin(
                f"{GALAXY_ANSIBLE_BASE_URL}/api/v2/collections/",
                ANSIBLE_DEMO_COLLECTION.replace(".", "/"),
            )
        )
        pulp_collection_data = client.get(
            urljoin(f"{url}/api/v2/collections/", ANSIBLE_DEMO_COLLECTION.replace(".", "/"))
        )

        galaxy_keys = [i for i in galaxy_collection_data.keys() if i != "deprecated"].sort()
        pulp_keys = [*pulp_collection_data].sort()
        self.assertEqual(galaxy_keys, pulp_keys)
