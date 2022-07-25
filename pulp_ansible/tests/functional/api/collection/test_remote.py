"""Tests related to CollectionRemote objects."""
import pytest
from pulpcore.client.pulp_ansible.exceptions import ApiException
from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import gen_ansible_remote


@pytest.mark.parallel
def test_remote_with_url_only_is_allowed(
    ansible_remote_collection_api_client, gen_object_with_cleanup
):
    """Assert that a `CollectionRemote` with only a url can be created."""
    body = gen_ansible_remote(url="https://example.com/")
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)
    assert remote.url == "https://example.com/"


@pytest.mark.parallel
def test_token_only_is_allowed(ansible_remote_collection_api_client, gen_object_with_cleanup):
    """Assert that a `CollectionRemote` with `token` and no `auth_url` can be created."""
    body = gen_ansible_remote(url="https://example.com/", token="this is a token string")
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)
    assert remote.token == "this is a token string"


@pytest.mark.parallel
def test_update_auth_url(ansible_remote_collection_api_client, gen_object_with_cleanup):
    """Assert that a `CollectionRemote` with `token` and no `auth_url` can be created."""
    body = gen_ansible_remote(
        url="https://example.com/",
        token="this is a token string",
        auth_url="https://example.com",
    )
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)
    response = ansible_remote_collection_api_client.partial_update(
        remote.pulp_href, {"auth_url": None}
    )
    monitor_task(response.task)
    remote = ansible_remote_collection_api_client.read(remote.pulp_href)
    assert remote.auth_url is None
    response = ansible_remote_collection_api_client.partial_update(
        remote.pulp_href, {"auth_url": "https://example.com"}
    )
    monitor_task(response.task)
    remote = ansible_remote_collection_api_client.read(remote.pulp_href)
    assert remote.auth_url == "https://example.com"


@pytest.mark.parallel
def test_auth_url_requires_token(ansible_remote_collection_api_client):
    """Assert that a `CollectionRemote` with `auth_url` and no `token` can't be created."""
    body = gen_ansible_remote(url="https://example.com/", auth_url="https://example.com")
    with pytest.raises(ApiException) as e:
        ansible_remote_collection_api_client.create(body)
        assert e.value.reason == "When specifying 'auth_url' you must also specify 'token'."


@pytest.mark.parallel
def test_remote_urls(ansible_remote_collection_api_client, gen_object_with_cleanup):
    """This tests that the remote url ends with a "/"."""
    body = gen_ansible_remote(url="http://galaxy.ansible.com/api")
    with pytest.raises(ApiException) as e:
        ansible_remote_collection_api_client.create(body)
        assert "Ensure the URL ends '/'." in e.value.reason

    body = gen_ansible_remote(url="http://galaxy.example.com")
    with pytest.raises(ApiException) as e:
        ansible_remote_collection_api_client.create(body)
        assert "Ensure the URL ends '/'." in e.value.reason

    body = gen_ansible_remote(url="https://galaxy.ansible.com")
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)
    assert remote.url == "https://galaxy.ansible.com"

    body = gen_ansible_remote(url="https://galaxy.ansible.com/")
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)
    assert remote.url == "https://galaxy.ansible.com/"
