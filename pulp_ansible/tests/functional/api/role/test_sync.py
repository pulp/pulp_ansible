import pytest

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_ansible.tests.functional.constants import ANSIBLE_FIXTURE_CONTENT_SUMMARY


@pytest.mark.parallel
def test_role_sync(
    ansible_repo_version_api_client,
    ansible_repo_factory,
    ansible_role_remote_factory,
    ansible_sync_factory,
):
    repository = ansible_repo_factory()
    remote = ansible_role_remote_factory()
    assert repository.latest_version_href == repository.pulp_href + "versions/0/"

    repository = ansible_sync_factory(repository, remote=remote.pulp_href)
    assert repository.latest_version_href == repository.pulp_href + "versions/1/"
    version = ansible_repo_version_api_client.read(repository.latest_version_href)
    assert {
        k: v["count"] for k, v in version.content_summary.present.items()
    } == ANSIBLE_FIXTURE_CONTENT_SUMMARY
    assert {
        k: v["count"] for k, v in version.content_summary.added.items()
    } == ANSIBLE_FIXTURE_CONTENT_SUMMARY

    repository = ansible_sync_factory(repository, remote=remote.pulp_href)
    assert repository.latest_version_href == repository.pulp_href + "versions/1/"


@pytest.mark.parallel
def test_role_sync_invalid(ansible_repo_factory, ansible_role_remote_factory, ansible_sync_factory):
    remote = ansible_role_remote_factory(url="http://i-am-an-invalid-url.com/invalid/")

    with pytest.raises(PulpTaskError) as exc_info:
        ansible_sync_factory(remote=remote.pulp_href)
    assert (
        exc_info.value.task.error["description"]
        == "Could not determine API version for: http://i-am-an-invalid-url.com/invalid/"
    )
