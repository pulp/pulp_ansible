"""Tests that CRUD remotes."""

import pytest
import uuid

from pulpcore.client.pulp_ansible import ApiException


@pytest.mark.parallel
def test_crud_role_remote(ansible_bindings, ansible_role_remote_factory, monitor_task):
    # Create a remote.
    remote = ansible_role_remote_factory(
        password=str(uuid.uuid4()),
        username=str(uuid.uuid4()),
        policy="immediate",
    )
    # Try to create a second remote with an identical name.
    with pytest.raises(ApiException):
        ansible_role_remote_factory(name=remote.name)
    # Update a remote using HTTP PATCH.
    new_values = {
        "url": "http://" + str(uuid.uuid4()),
        "username": str(uuid.uuid4()),
        "password": str(uuid.uuid4()),
        "policy": "immediate",
    }
    monitor_task(ansible_bindings.RemotesRoleApi.partial_update(remote.pulp_href, new_values).task)
    # Test read remote
    remote_read = ansible_bindings.RemotesRoleApi.read(remote.pulp_href)
    assert remote_read.name == remote.name
    assert remote_read.url == new_values["url"]
    assert remote_read.policy == new_values["policy"]
    # Update a remote using HTTP PUT.
    new_values = {
        "name": str(uuid.uuid4()),
        "url": "http://" + str(uuid.uuid4()),
        "username": str(uuid.uuid4()),
        "password": str(uuid.uuid4()),
        "policy": "immediate",
    }
    monitor_task(ansible_bindings.RemotesRoleApi.update(remote.pulp_href, new_values).task)
    # Test read remotes
    remotes = ansible_bindings.RemotesRoleApi.list(name=new_values["name"]).results
    assert remotes[0].name == new_values["name"]
    assert remotes[0].url == new_values["url"]
    assert remotes[0].policy == new_values["policy"]
    # Test delete remote
    monitor_task(ansible_bindings.RemotesRoleApi.delete(remote.pulp_href).task)
