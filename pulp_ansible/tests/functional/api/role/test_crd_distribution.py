"""CRUD tests for AnsibleDistribution."""

import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors
from pulp_smash.pulp3.utils import gen_distribution, gen_remote, gen_repo, sync
from pulp_smash.pulp3.bindings import PulpTestCase

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_ELASTIC_FIXTURE_URL,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_REPO_PATH,
)
from pulp_ansible.tests.functional.utils import skip_if
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class RepositoryVersionDistributionTestCase(PulpTestCase):
    """Test AnsibleDistribution using repo and repo_version.

    This test targets the following issue:

    `Pulp #4846 <https://pulp.plan.io/issues/4846>`_

    Do the following:

    1. Create a repo and repo_version with at least 1 ansible content synced.
    2. Create a AnsibleDistribution with 'repository' field set to the
       repository from step 1. Verify it accepts it.
    3. Update the AnsibleDistribution to unset 'repository' and set
       'repository_version'. Verify it accepts it.
    4. Update the AnsibleDistribution to set both 'repository' and
       'repository_version' and verify it rejects it. These options cannot be
       used together.
    5. Attempt to update AnsibleDistribution to set repository to invalid
       repository path ans verify it rejects it.
    """

    @classmethod
    def setUpClass(cls):
        """Define class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)
        cls.repo = {}
        cls.distribution = {}

    def test_01_positive_create_and_sync_repo_and_repo_version(self):
        """Create a repo and repo_version with synced content."""
        self.repo.update(self.client.post(ANSIBLE_REPO_PATH, gen_repo()))

        remote = self.client.post(ANSIBLE_REMOTE_PATH, gen_remote(url=ANSIBLE_ELASTIC_FIXTURE_URL))

        self.addCleanup(self.client.delete, remote["pulp_href"])

        self.assertEqual(self.repo["latest_version_href"], f"{self.repo['pulp_href']}versions/0/")
        sync(self.cfg, remote, self.repo)

        self.repo.update(self.client.get(self.repo["pulp_href"]))
        self.assertIsNotNone(self.repo["latest_version_href"])

    @skip_if(bool, "repo", False)
    def test_02_positive_create_distribution_with_repo(self):
        """Create a distribution with 'repository' field set to repo."""
        distribution = self.client.post(
            ANSIBLE_DISTRIBUTION_PATH, gen_distribution(repository=self.repo["pulp_href"])
        )
        self.distribution.update(self.client.get(distribution["pulp_href"]))

        self.assertEqual(self.distribution["repository"], self.repo["pulp_href"])
        self.assertIsNone(self.distribution["repository_version"])

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_03_negative_update_distribution_with_invalid_repo(self):
        """Assert invalid repo raises invalid hyperlink error."""
        with self.assertRaises(HTTPError):
            self.client.patch(
                self.distribution["pulp_href"], {"repository": "this-is-invalid-repository"}
            )

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_03_positive_partial_update_distribution_to_use_repo_version(self):
        """Patch a distribution with 'repository_version' field set."""
        # Patch repository to None
        self.client.patch(self.distribution["pulp_href"], {"repository": None})

        # Patch repository version
        self.distribution.update(
            self.client.patch(
                self.distribution["pulp_href"],
                {"repository_version": self.repo["latest_version_href"]},
            )
        )

        self.assertEqual(self.distribution["repository_version"], self.repo["latest_version_href"])
        self.assertIsNone(self.distribution["repository"])

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_04_positive_full_update_distribution_to_use_repo_version(self):
        """Put a distribution with 'repository_version' field set."""
        new_dist = self.distribution.copy()
        new_dist["repository_version"] = self.repo["latest_version_href"]
        del new_dist["repository"]
        del self.distribution["repository"]

        self.distribution.update(self.client.put(self.distribution["pulp_href"], new_dist))

        self.assertEqual(self.distribution["repository_version"], self.repo["latest_version_href"])

        self.assertIsNone(self.distribution["repository"])

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_05_positive_full_update_distribution_to_use_repo(self):
        """Put a distribution with 'repository' field set."""
        if not selectors.bug_is_fixed(4910, self.cfg.pulp_version):
            raise unittest.SkipTest("Issue 4910 is not resolved")

        new_dist = self.distribution.copy()
        new_dist["repository"] = self.repo["pulp_href"]
        del new_dist["repository_version"]
        del self.distribution["repository_version"]

        response = self.client.using_handler(api.echo_handler).put(
            self.distribution["pulp_href"], new_dist
        )

        self.assertEqual(response.status_code, 400, response)

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_06_negative_update_distribution_with_repo_and_version(self):
        """Assert 'repo' and 'repo_version' cannot be used together."""
        new_dist = self.distribution.copy()
        new_dist["repository_version"] = self.repo["latest_version_href"]
        new_dist["repository"] = self.repo["pulp_href"]
        with self.assertRaises(HTTPError):
            self.client.put(self.distribution["pulp_href"], new_dist)

    @skip_if(bool, "distribution", False)
    @skip_if(bool, "repo", False)
    def test_07_negative_create_distribution_after_repo_is_deleted(self):
        """Assert distribution cannot be created with deleted repo."""
        self.client.delete(self.repo["pulp_href"])

        response = self.client.using_handler(api.echo_handler).patch(
            self.distribution["pulp_href"], {"repository": self.repo["pulp_href"]}
        )
        self.assertEqual(response.status_code, 400)

        # '{"repository":["Invalid hyperlink - Object does not exist."]}'
        for msg in ("invalid", "hyperlink", "object", "not", "exist"):
            self.assertIn(msg, str(response.content).lower())

    @skip_if(bool, "distribution", False)
    def test_08_positive_delete_distribution(self):
        """Delete a distribution."""
        self.client.delete(self.distribution["pulp_href"])
        with self.assertRaises(HTTPError):
            self.client.get(self.distribution["pulp_href"])
