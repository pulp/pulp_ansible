"""Tests that CRUD remotes."""
import pytest
from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
)
from pulpcore.client.pulp_ansible import ApiException


@pytest.mark.parallel
def test_crud_git_remote(ansible_remote_git_api_client, gen_object_with_cleanup):
    """Create, Read, Partial Update, and Delete an Ansible Git remote."""
    # Create Git remote
    body = gen_ansible_remote(url="https://github.com/geerlingguy/ansible-role-adminer.git")
    remote = gen_object_with_cleanup(ansible_remote_git_api_client, body)

    # Read Git remote
    remote = ansible_remote_git_api_client.read(remote.pulp_href)
    for k, v in body.items():
        assert body[k] == getattr(remote, k)

    # Update Git remote
    update_body = {"url": "https://github.com/geerlingguy/ansible-role-ansible.git"}
    remote_update = ansible_remote_git_api_client.partial_update(remote.pulp_href, update_body)
    monitor_task(remote_update.task)
    remote = ansible_remote_git_api_client.read(remote.pulp_href)
    assert remote.url == update_body["url"]
    assert remote.metadata_only is False

    # Ensure Git remote doesn't have a download policy
    assert not hasattr(remote, "policy")

    # Delete Git remote
    remote_delete = ansible_remote_git_api_client.delete(remote.pulp_href)
    monitor_task(remote_delete.task)
    with pytest.raises(ApiException):
        ansible_remote_git_api_client.read(remote.pulp_href)


@pytest.mark.parallel
def test_git_metadata_only_remote(ansible_git_remote_factory):
    """Create a remote where `metadata_only` is set to True."""
    body = gen_ansible_remote(
        url="https://github.com/geerlingguy/ansible-role-adminer.git", metadata_only=True
    )
    remote = ansible_git_remote_factory(**body)
    for k, v in body.items():
        assert body[k] == getattr(remote, k)
