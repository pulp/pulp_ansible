import pytest
from pulpcore.client.pulp_ansible.exceptions import ApiException


@pytest.mark.parallel
def test_remote_with_url_only_is_allowed(ansible_collection_remote_factory):
    """Assert that a `CollectionRemote` with only a url can be created."""
    ansible_collection_remote_factory(url="https://example.com/")


@pytest.mark.parallel
def test_token_only_is_allowed(ansible_collection_remote_factory):
    """Assert that a `CollectionRemote` with `token` and no `auth_url` can be created."""
    ansible_collection_remote_factory(url="https://example.com/", token="this is a token string")


@pytest.mark.parallel
def test_update_auth_url(
    ansible_remote_collection_api_client, ansible_collection_remote_factory, monitor_task
):
    """Assert that a `CollectionRemote` with `token` and no `auth_url` can be created."""
    remote = ansible_collection_remote_factory(
        url="https://example.com/",
        token="this is a token string",
        auth_url="https://example.com",
    )
    assert not hasattr(remote, "token")
    monitor_task(
        ansible_remote_collection_api_client.partial_update(
            remote.pulp_href, {"auth_url": None}
        ).task
    )
    monitor_task(
        ansible_remote_collection_api_client.partial_update(
            remote.pulp_href, {"auth_url": "https://example.com"}
        ).task
    )


@pytest.mark.parallel
def test_auth_url_requires_token(ansible_collection_remote_factory):
    """Assert that a `CollectionRemote` with `auth_url` and no `token` can't be created."""
    with pytest.raises(ApiException) as exc_info:
        ansible_collection_remote_factory(
            url="https://example.com/", auth_url="https://example.com"
        )
    assert exc_info.value.status == 400
    assert "When specifying 'auth_url' you must also specify 'token'." in exc_info.value.body


@pytest.mark.parallel
def test_remote_urls(ansible_collection_remote_factory):
    """This tests that the remote url ends with a "/"."""
    with pytest.raises(ApiException):
        ansible_collection_remote_factory(url="http://galaxy.ansible.com/api")

    with pytest.raises(ApiException):
        ansible_collection_remote_factory(url="http://galaxy.example.com")

    ansible_collection_remote_factory(url="https://galaxy.ansible.com")
    ansible_collection_remote_factory(url="https://galaxy.ansible.com/")
