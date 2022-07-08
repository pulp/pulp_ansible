"""Tests that Roles hosted by Pulp can be installed by ansible-galaxy."""

import json
import pytest
import subprocess

from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import TestCaseUsingBindings
from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DOCKER_ROLE_NAMESPACE,
    ANSIBLE_DOCKER_ROLE_NAME,
    ANSIBLE_DOCKER_ROLE_REPO,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


# @pytest.mark.parallel
def test_role_import(
    delete_orphans_pre,
    ansible_bindings_client,
    ansible_galaxy_roles_api_client,
    ansible_repo_api_client,
    ansible_distributions_api_client,
    gen_object_with_cleanup
):
    """
    Verifies the api/v1/imports view is functional.
    """
    # Create the legacy repo if needed
    repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": "legacy"})

    # Create the legacy distribution if needed
    body = {
        "name": "legacy",
        "base_path": "legacy",
    }
    body["repository"] = repo.pulp_href
    distribution = gen_object_with_cleanup(ansible_distributions_api_client, body)

    # We expect the http[s]://<host>:<port>/api/v1 endpoint to be available,
    # so no special distribution based url will be used. The import view
    # should take care of defaulting to the "legacy" distribution.
    client = ansible_repo_api_client.api_client
    server_url = client.configuration.host.rstrip("/") + "/"

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
    assert pid.returncode == 0

    # Fetch the first page of the v1 roles.
    v1_roles_p1 = ansible_galaxy_roles_api_client.get()

    # Ensure the imported role is in the list.
    expected_role = {
        "id": f"{ANSIBLE_DOCKER_ROLE_NAMESPACE}.{ANSIBLE_DOCKER_ROLE_NAME}",
        "name": ANSIBLE_DOCKER_ROLE_NAME,
        "namespace": ANSIBLE_DOCKER_ROLE_NAMESPACE,
    }
    assert expected_role in [x.to_dict() for x in v1_roles_p1.results]

    # Ensure it has a list of versions ...
    v_url = (
        "/api/v1/roles/"
        + f"{ANSIBLE_DOCKER_ROLE_NAMESPACE}.{ANSIBLE_DOCKER_ROLE_NAME}"
        + "/versions/"
    )
    # vpage1 = self.api_client.get(v_url)
    # import epdb; epdb.st()
    # vpage1 = client.get(v_url)
    # vpage1 = client.call_api(v_url, 'GET')
    resp = ansible_bindings_client.rest_client.GET(server_url.rstrip('/') + v_url)
    vpage1 = json.loads(resp.data)
    # import epdb; epdb.st()
    assert vpage1["count"] >= 1
