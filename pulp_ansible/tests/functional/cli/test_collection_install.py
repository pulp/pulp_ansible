"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""
from os import path
import subprocess
import tempfile
import unittest

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    AnsibleRepositorySyncURL,
    RemotesCollectionApi,
)
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import (
    gen_ansible_client,
    gen_ansible_remote,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class InstallCollectionTestCase(PulpTestCase):
    """Test whether ansible-galaxy can install a Collection hosted by Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        delete_orphans()
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)

    def create_install_scenario(self, body):
        """Create Install scenario."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
        repository_sync_data = AnsibleRepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)
        return distribution

    def perform_install_test(self, collection_name, distribution, extra_args=""):
        """Test that the collection can be installed from Pulp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = "ansible-galaxy collection install {} -c -s {} -p {} {}".format(
                collection_name, distribution.client_url, temp_dir, extra_args
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
        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
        distribution = self.create_install_scenario(body)
        self.perform_install_test(ANSIBLE_DEMO_COLLECTION, distribution)

    @unittest.skip("needs to use signing fixtures from pulpcore")
    def test_signature_collection_install(self):
        """Test whether ansible-galaxy can install a Collection w/ a signature hosted by Pulp."""
        create_signing_service = None  # Avoids flake8 complaining since this doesn't exist
        delete_signing_service = None  # Avoids flake8 complaining since this doesn't exist
        get_client_keyring = None  # Avoids flake8 complaining since this doesn't exist

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
        distribution = self.create_install_scenario(body)
        self.addCleanup(delete_orphans)
        repository_href = distribution.repository
        signing_service = create_signing_service()
        self.addCleanup(delete_signing_service, signing_service.name)
        # Switch this over to signature upload in the future
        signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}
        monitor_task(self.repo_api.sign(repository_href, signing_body).task)
        repo = self.repo_api.read(repository_href)
        self.assertEqual(repo.latest_version_href[-2], "2")

        keyring_arg = f"--keyring {get_client_keyring()}"
        self.perform_install_test(ANSIBLE_DEMO_COLLECTION, distribution, keyring_arg)
