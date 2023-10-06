import pytest
from pulp_smash.pulp3.bindings import monitor_task, PulpTaskError

from pulpcore.client.pulp_ansible import (
    AnsibleRepositorySyncURL,
)


def _sync_and_assert(
    remote, ansible_repo, ansible_repo_api_client, ansible_collection_version_api_client
):
    body = AnsibleRepositorySyncURL(remote=remote.pulp_href)
    monitor_task(ansible_repo_api_client.sync(ansible_repo.pulp_href, body).task)

    content_response = ansible_collection_version_api_client.list(
        repository_version=f"{ansible_repo.versions_href}1/"
    )
    assert content_response.count == 1


@pytest.mark.parallel
def test_sync_through_http_proxy(
    ansible_repo,
    ansible_collection_remote_factory,
    ansible_repo_api_client,
    ansible_collection_version_api_client,
    http_proxy,
):
    """
    Test syncing through a http proxy.
    """
    ansible_remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
        proxy_url=http_proxy.proxy_url,
    )

    _sync_and_assert(
        ansible_remote, ansible_repo, ansible_repo_api_client, ansible_collection_version_api_client
    )


@pytest.mark.parallel
def test_sync_through_http_proxy_with_auth(
    ansible_repo,
    ansible_collection_remote_factory,
    ansible_repo_api_client,
    ansible_collection_version_api_client,
    http_proxy_with_auth,
):
    """
    Test syncing through a http proxy that requires auth.
    """
    ansible_remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
        proxy_url=http_proxy_with_auth.proxy_url,
        proxy_username=http_proxy_with_auth.username,
        proxy_password=http_proxy_with_auth.password,
    )

    _sync_and_assert(
        ansible_remote, ansible_repo, ansible_repo_api_client, ansible_collection_version_api_client
    )


@pytest.mark.parallel
def test_sync_through_http_proxy_with_auth_but_auth_not_configured(
    ansible_repo,
    ansible_collection_remote_factory,
    ansible_repo_api_client,
    ansible_collection_version_api_client,
    http_proxy_with_auth,
):
    """
    Test syncing through a http proxy that requires auth, but auth is not configured.
    """
    ansible_remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
        proxy_url=http_proxy_with_auth.proxy_url,
    )

    try:
        _sync_and_assert(
            ansible_remote,
            ansible_repo,
            ansible_repo_api_client,
            ansible_collection_version_api_client,
        )
    except PulpTaskError as exc:
        assert "407, message='Proxy Authentication Required'" in exc.task.error["description"]
