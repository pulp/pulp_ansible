"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""
import os
from os import path
import subprocess
import tempfile
import unittest

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    RepositorySyncURL,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    AH_AUTH_URL,
    ANSIBLE_COLLECTION_TESTING_URL_V2,
    ANSIBLE_DEMO_COLLECTION,
    TOKEN_DEMO_COLLECTION,
    TOKEN_AUTH_COLLECTION_TESTING_URL,
)
from pulp_ansible.tests.functional.utils import (
    gen_ansible_client,
    gen_ansible_remote,
    monitor_task,
)
from pulp_ansible.tests.functional.utils import skip_if
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class InstallCollectionTestCase(unittest.TestCase):
    """Test whether ansible-galaxy can install a Collection hosted by Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.AH_token = "AUTOMATION_HUB_TOKEN_AUTH" in os.environ
        cls.CI_AH_token = "CI_AUTOMATION_HUB_TOKEN_AUTH" in os.environ
        cls.GH_token = "GITHUB_API_KEY" in os.environ
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)

    def create_install_scenario(self, body, collection_name):
        """Create Install scenario."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

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
            # FIXME Use --no-deps while https://pulp.plan.io/issues/7751 is not addressed
            cmd = "ansible-galaxy collection install {} -c -s {} -p {} --no-deps".format(
                collection_name, distribution.client_url, temp_dir
            )

            directory = "{}/ansible_collections/{}".format(
                temp_dir, collection_name.replace(".", "/")
            )

            self.assertTrue(
                not path.exists(directory), "Directory {} already exists".format(directory)
            )

            subprocess.run(cmd.split())

            self.assertTrue(path.exists(directory), "Could not find directory {}".format(directory))

    def test_install_collection(self):
        """Test whether ansible-galaxy can install a Collection hosted by Pulp."""
        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL_V2)
        self.create_install_scenario(body, ANSIBLE_DEMO_COLLECTION)

    @skip_if(bool, "AH_token", False)
    def test_install_collection_with_token_from_automation_hub(self):
        """Test whether ansible-galaxy can install a Collection hosted by Pulp."""
        body = gen_ansible_remote(
            url=TOKEN_AUTH_COLLECTION_TESTING_URL,
            auth_url=AH_AUTH_URL,
            token=os.environ["AUTOMATION_HUB_TOKEN_AUTH"],
            tls_validation=False,
        )
        self.create_install_scenario(body, TOKEN_DEMO_COLLECTION)

    @skip_if(bool, "CI_AH_token", False)
    def test_install_collection_with_token_from_ci_automation_hub(self):
        """Test whether ansible-galaxy can install a Collection hosted by Pulp."""
        name = "collection_dep_a_fdqqyxou"
        namespace = "autohubtest2"
        aurl = "https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"

        body = gen_ansible_remote(
            url=f"https://ci.cloud.redhat.com/api/automation-hub/v3/collections/{namespace}/{name}",
            auth_url=aurl,
            token=os.environ["CI_AUTOMATION_HUB_TOKEN_AUTH"],
            tls_validation=False,
        )
        self.create_install_scenario(body, f"{namespace}.{name}")

    @skip_if(bool, "GH_token", False)
    def test_install_collection_with_token_from_galaxy(self):
        """Test whether ansible-galaxy can install a Collection hosted by Pulp."""
        token = os.environ["GITHUB_API_KEY"]
        PULP_COLLECTION = ANSIBLE_COLLECTION_TESTING_URL_V2.replace("testing", "pulp")
        PULP_COLLECTION = PULP_COLLECTION.replace("k8s_demo_collection", "pulp_installer")

        body = gen_ansible_remote(url=PULP_COLLECTION, token=token)
        self.create_install_scenario(body, "pulp.pulp_installer")
