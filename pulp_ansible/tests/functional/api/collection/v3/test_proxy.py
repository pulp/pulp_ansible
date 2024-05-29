import pytest
from pulpcore.tests.functional.utils import PulpTaskError

from pulpcore.client.pulp_ansible import (
    AnsibleRepositorySyncURL,
)


def _sync_and_assert(
    ansible_bindings,
    remote,
    ansible_repo,
    monitor_task,
):
    body = AnsibleRepositorySyncURL(remote=remote.pulp_href)
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sync(ansible_repo.pulp_href, body).task)

    content_response = ansible_bindings.ContentCollectionVersionsApi.list(
        repository_version=f"{ansible_repo.versions_href}1/"
    )
    assert content_response.count == 1


@pytest.mark.parallel
def test_sync_through_http_proxy(
    ansible_bindings,
    ansible_repo,
    ansible_collection_remote_factory,
    http_proxy,
    monitor_task,
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
        ansible_bindings,
        ansible_remote,
        ansible_repo,
        monitor_task,
    )


@pytest.mark.parallel
def test_sync_through_http_proxy_with_auth(
    ansible_bindings,
    ansible_repo,
    ansible_collection_remote_factory,
    http_proxy_with_auth,
    monitor_task,
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
        ansible_bindings,
        ansible_remote,
        ansible_repo,
        monitor_task,
    )


@pytest.mark.parallel
def test_sync_through_http_proxy_with_auth_but_auth_not_configured(
    ansible_bindings,
    ansible_repo,
    ansible_collection_remote_factory,
    http_proxy_with_auth,
    monitor_task,
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
            ansible_bindings,
            ansible_remote,
            ansible_repo,
            monitor_task,
        )
    except PulpTaskError as exc:
        assert "407, message='Proxy Authentication Required'" in exc.task.error["description"]
