"""Tests related to sync ansible plugin collection content type."""
import pytest

from tempfile import NamedTemporaryFile
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task
from pulp_smash.utils import http_get

from pulpcore.client.pulp_ansible.exceptions import ApiException


from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote


def test_tags_filter(
    ansible_repo,
    sync_repo_factory,
    ansible_collection_remote_factory,
    ansible_collection_version_api_client,
):
    """Filter CollectionVersions by using the tags filter.

    This test targets the following issue:

    * `Pulp #5571 <https://pulp.plan.io/issues/5571>`_

    Do the following:

    1. Create a repository, and a remote.
    2. Sync the remote.
    3. Attempt to filter the CollectionVersions by different tags

    Note that the testing.k8s_demo_collection collection has tags 'k8s' and 'kubernetes'.
    """
    body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
    remote = ansible_collection_remote_factory(**body)

    # Sync the repository.
    repo = sync_repo_factory(ansible_repo, remote=remote.pulp_href)

    cv_api = ansible_collection_version_api_client  # shorten some lines
    # filter collection versions by tags
    collections = cv_api.list(repository_version=repo.latest_version_href, tags="nada")
    assert collections.count == 0

    collections = cv_api.list(repository_version=repo.latest_version_href, tags="k8s")
    assert collections.count == 1

    collections = cv_api.list(repository_version=repo.latest_version_href, tags="k8s,kubernetes")
    assert collections.count == 1

    collections = cv_api.list(repository_version=repo.latest_version_href, tags="nada,k8s")
    assert collections.count == 0


def test_crud_collection_versions(ansible_collection_version_api_client):
    """CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp #3445 <https://pulp.plan.io/issues/3445>`_
    * `Pulp Smash #870 <https://github.com/pulp/pulp-smash/issues/870>`_
    """
    delete_orphans()
    cv_api = ansible_collection_version_api_client

    def upload_collection():
        """Upload collection."""
        url = "https://galaxy.ansible.com/download/pulp-squeezer-0.0.9.tar.gz"
        collection_content = http_get(url)
        with NamedTemporaryFile() as temp_file:
            temp_file.write(collection_content)
            response = cv_api.create(
                file=temp_file.name, namespace="pulp", name="squeezer", version="0.0.9"
            )
            created_resources = monitor_task(response.task).created_resources
            return cv_api.read(created_resources[0])

    # Create a collection version
    attrs = dict(namespace="pulp", name="squeezer", version="0.0.9")
    content_unit = upload_collection().to_dict()
    for key, val in attrs.items():
        assert content_unit[key] == val

    # Read a content unit by its href.
    content_unit = cv_api.read(content_unit["pulp_href"]).to_dict()
    for key, val in content_unit.items():
        assert content_unit[key] == val

    # Read a content unit by its pkg_id.
    page = cv_api.list(namespace=content_unit["namespace"], name=content_unit["name"])
    assert page.count == 1
    for key, val in content_unit.items():
        assert page.results[0].to_dict()[key] == val

    # Attempt to update a content unit using HTTP PATCH. Not supported should error.
    attrs = {"name": "testing"}
    with pytest.raises(AttributeError) as exc:
        cv_api.partial_update(content_unit["pulp_href"], attrs)
    msg = "object has no attribute 'partial_update'"
    assert msg in exc.value.args[0]

    # Attempt to update a content unit using HTTP PUT. Not supported should error.
    attrs = {"name": "testing"}
    with pytest.raises(AttributeError) as exc:
        cv_api.update(content_unit["pulp_href"], attrs)
    msg = "object has no attribute 'update'"
    assert msg in exc.value.args[0]

    # Attempt to delete a content unit using HTTP DELETE. Not supported should error?
    with pytest.raises(AttributeError) as exc:
        cv_api.delete(content_unit["pulp_href"])
    msg = "object has no attribute 'delete'"
    assert msg in exc.value.args[0]

    with pytest.raises(ApiException) as ctx:
        upload_collection()
    assert "The fields namespace, name, version must make a unique set." in ctx.value.body

    delete_orphans()
