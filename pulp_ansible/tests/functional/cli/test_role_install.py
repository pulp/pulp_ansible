"""Tests that Roles hosted by Pulp can be installed by ansible-galaxy."""

from os import path
import subprocess

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_ELASTIC_FIXTURE_URL,
    ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME,
    ANSIBLE_ELASTIC_ROLE,
)


def test_install_role(
    ansible_distribution_factory,
    ansible_role_remote_factory,
    ansible_sync_factory,
    ansible_dir_factory,
):
    """Test whether ansible-galaxy can install a Role hosted by Pulp."""
    distribution = ansible_distribution_factory(
        repository=ansible_sync_factory(
            remote=ansible_role_remote_factory(url=ANSIBLE_ELASTIC_FIXTURE_URL).pulp_href
        )
    )

    ansible_dir = ansible_dir_factory(distribution.client_url)
    directory = ansible_dir / ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME

    assert not path.exists(directory), "Directory {} already exists".format(directory)
    subprocess.run(
        (
            "ansible-galaxy",
            "role",
            "install",
            ANSIBLE_ELASTIC_ROLE,
            "-c",
            "-p",
            ansible_dir,
        ),
        check=True,
    )

    assert path.exists(directory), "Could not find directory {}".format(directory)
