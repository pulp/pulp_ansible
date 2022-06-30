"""Tests that Roles hosted by Pulp can be installed by ansible-galaxy."""

from os import path
import subprocess
import tempfile

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    AnsibleRepositorySyncURL,
    RemotesRoleApi,
)
from pulp_smash.pulp3.bindings import monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DOCKER_FIXTURE_URL,
    ANSIBLE_DOCKER_ROLE_NAMESPACE_NAME,
    ANSIBLE_DOCKER_ROLE_NAMESPACE,
    ANSIBLE_DOCKER_ROLE_NAME,
    ANSIBLE_DOCKER_ROLE_REPO,
    ANSIBLE_DOCKER_ROLE,
)
from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ImportRoleTestCase(PulpTestCase):
    """Test whether ansible-galaxy can import a role into pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.remote_role_api = RemotesRoleApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)

    def test_import_role(self):

        # Create the legacy repo if needed
        legacy_repo_check = self.repo_api.list(name='legacy')
        if legacy_repo_check.count == 1:
            repo = legacy_repo_check.results[0]
        else:
            repo = self.repo_api.create({'name': 'legacy'})
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create the legacy distribution if needed
        legacy_dist_check = self.distributions_api.list(name='legacy')
        if legacy_dist_check.count == 1:
            distribution = legacy_dist_check.results[0]
        else:
            body = {
                'name': 'legacy',
                'base_path': 'legacy',
            }
            body["repository"] = repo.pulp_href
            distribution_create = self.distributions_api.create(body)
            created_resources = monitor_task(distribution_create.task).created_resources
            distribution = self.distributions_api.read(created_resources[0])
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        # We expect the http[s]://<host>:<port>/api/v1 endpoint to be available,
        # so no special distribution based url will be used. The import view
        # should take care of defaulting to the "legacy" distribution.
        server_url = self.client.configuration.host.rstrip('/') + '/'

        cmd = [
            "ansible-galaxy",
            "role",
            "import",
            "-vvvv",
            ANSIBLE_DOCKER_ROLE_NAMESPACE,
            ANSIBLE_DOCKER_ROLE_REPO,
            "-c",
            "-s",
            server_url,
        ]
        pid = subprocess.run(cmd)
        assert pid.returncode == 0
