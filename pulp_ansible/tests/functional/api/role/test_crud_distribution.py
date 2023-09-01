"""CRUD tests for AnsibleDistribution."""

import pytest
from collections import namedtuple

from pulpcore.client.pulp_ansible import ApiException


FakeRepository = namedtuple("FakeRepository", "pulp_href")


@pytest.mark.parallel
def test_crud_distribution(
    ansible_distro_api_client,
    ansible_role_remote_factory,
    ansible_sync_factory,
    ansible_distribution_factory,
    monitor_task,
    has_pulp_plugin,
):
    repository = ansible_sync_factory(remote=ansible_role_remote_factory().pulp_href)
    distribution = ansible_distribution_factory(repository=repository)
    assert distribution.repository == repository.pulp_href
    assert distribution.repository_version is None

    with pytest.raises(ApiException) as exc_info:
        fake_repository = FakeRepository(
            pulp_href=repository.pulp_href[:-37] + "00000000-0000-0000-0000-000000000000/"
        )
        ansible_distribution_factory(repository=fake_repository)
    assert "Invalid hyperlink - Object does not exist." in exc_info.value.body

    with pytest.raises(ApiException) as exc_info:
        ansible_distro_api_client.partial_update(
            distribution.pulp_href, {"repository": "this-is-invalid"}
        )
    assert "Invalid hyperlink - No URL match." in exc_info.value.body

    ansible_distro_api_client.partial_update(distribution.pulp_href, {"repository": None})
    monitor_task(
        ansible_distro_api_client.partial_update(
            distribution.pulp_href, {"repository_version": repository.latest_version_href}
        ).task
    )
    distribution = ansible_distro_api_client.read(distribution.pulp_href)
    assert distribution.repository is None
    assert distribution.repository_version == repository.latest_version_href

    if has_pulp_plugin("pulpcore", min="3.30.1"):
        # On older versions, this fails complaining repository and version cannot be used together.
        body = {
            "name": distribution.name,
            "base_path": distribution.base_path,
            "repository": repository.pulp_href,
        }
        monitor_task(ansible_distro_api_client.update(distribution.pulp_href, body).task)
        distribution = ansible_distro_api_client.read(distribution.pulp_href)
        assert distribution.repository == repository.pulp_href
        assert distribution.repository_version is None

    body = {
        "name": distribution.name,
        "base_path": distribution.base_path,
        "repository": repository.pulp_href,
        "repository_version": repository.latest_version_href,
    }
    with pytest.raises(ApiException) as exc_info:
        ansible_distro_api_client.update(distribution.pulp_href, body)
    assert (
        "Only one of the attributes 'repository' and 'repository_version' "
        "may be used simultaneously."
    ) in exc_info.value.body

    monitor_task(ansible_distro_api_client.delete(distribution.pulp_href).task)
    with pytest.raises(ApiException) as exc_info:
        ansible_distro_api_client.delete(distribution.pulp_href)
    assert "Not found." in exc_info.value.body
