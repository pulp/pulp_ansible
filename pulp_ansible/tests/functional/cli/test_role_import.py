"""Tests that Roles hosted by Pulp can be installed by ansible-galaxy."""

import subprocess

from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import TestCaseUsingBindings
from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DOCKER_ROLE_NAMESPACE,
    ANSIBLE_DOCKER_ROLE_NAME,
    ANSIBLE_DOCKER_ROLE_REPO,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ImportRoleTestCase(TestCaseUsingBindings):
    """Test whether ansible-galaxy can import a role into pulp."""

    def test_import_role(self):
        """
        Verifies the api/v1/imports view is functional.
        """
        # Create the legacy repo if needed
        legacy_repo_check = self.repo_api.list(name="legacy")
        if legacy_repo_check.count == 1:
            repo = legacy_repo_check.results[0]
        else:
            repo = self.repo_api.create({"name": "legacy"})
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create the legacy distribution if needed
        legacy_dist_check = self.distributions_api.list(name="legacy")
        if legacy_dist_check.count == 1:
            distribution = legacy_dist_check.results[0]
        else:
            body = {
                "name": "legacy",
                "base_path": "legacy",
            }
            body["repository"] = repo.pulp_href
            distribution_create = self.distributions_api.create(body)
            created_resources = monitor_task(distribution_create.task).created_resources
            distribution = self.distributions_api.read(created_resources[0])
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        # We expect the http[s]://<host>:<port>/api/v1 endpoint to be available,
        # so no special distribution based url will be used. The import view
        # should take care of defaulting to the "legacy" distribution.
        server_url = self.client.configuration.host.rstrip("/") + "/"

        # Ensure the galaxy cli can import the role without error ...
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
        self.assertEqual(pid.returncode, 0)

        """ content roles api has no delete function?
        # get the content view's pulp_href for cleanup?
        c_roles = self.content_roles_api.list()
        for c_role in c_roles.results:
            if (
                c_role.namespace == ANSIBLE_DOCKER_ROLE_NAMESPACE
                and c_role.name == ANSIBLE_DOCKER_ROLE_NAME
            ):
                self.addCleanup(self.content_roles_api.delete, c_role.pulp_href)
                break
        """

        # Fetch the first page of the v1 roles.
        v1_roles_p1 = self.galaxy_roles_api.get()

        # Ensure the imported role is in the list.
        expected_role = {
            "id": f"{ANSIBLE_DOCKER_ROLE_NAMESPACE}.{ANSIBLE_DOCKER_ROLE_NAME}",
            "name": ANSIBLE_DOCKER_ROLE_NAME,
            "namespace": ANSIBLE_DOCKER_ROLE_NAMESPACE,
        }
        self.assertIn(expected_role, [x.to_dict() for x in v1_roles_p1.results])

        # Ensure it has a list of versions ...
        v_url = (
            server_url
            + "api/v1/roles/"
            + f"{ANSIBLE_DOCKER_ROLE_NAMESPACE}.{ANSIBLE_DOCKER_ROLE_NAME}"
            + "/versions/"
        )
        vpage1 = self.api_client.get(v_url)
        self.assertGreaterEqual(vpage1["count"], 1)
