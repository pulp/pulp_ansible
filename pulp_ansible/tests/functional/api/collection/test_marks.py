import pytest
from pulp_smash.pulp3.utils import (
    get_added_content_summary,
    get_content,
    get_content_summary,
    get_removed_content_summary,
)
from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
)
from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL


def test_add_mark_to_collection_version(
    build_and_upload_collection,
    ansible_repo_api_client,
    ansible_repo,
    ansible_collection_mark_client,
    monitor_task,
):
    """Test adding a mark to a collection version.

    1. Build and upload a collection
    2. Add it to a repo version
    3. Add a mark to the collection version
    4. Assert the mark was added correctly
    5. Remove the mark
    6. Assert the mark was removed correctly
    """
    collection, collection_url = build_and_upload_collection()

    # add it to a repo version
    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_repo_api_client.modify(ansible_repo.pulp_href, body).task)
    ansible_repo = ansible_repo_api_client.read(ansible_repo.pulp_href)

    # assert the content was added correctly
    assert ansible_repo.latest_version_href.endswith("/1/")
    assert get_content_summary(ansible_repo.to_dict()) == {"ansible.collection_version": 1}

    # Add a mark to the collection version
    body = {"content_units": [collection_url], "value": "testable"}
    monitor_task(ansible_repo_api_client.mark(ansible_repo.pulp_href, body).task)
    ansible_repo = ansible_repo_api_client.read(ansible_repo.pulp_href)

    # assert the repo version incremented
    assert ansible_repo.latest_version_href.endswith("/2/")
    # Ensure mark with value "testable" is present on the marks
    marks = ansible_collection_mark_client.list(marked_collection=collection_url).results
    assert len(marks) == 1
    assert marks[0].value == "testable"
    assert marks[0].marked_collection == collection_url

    # Ensure mark is added to the repo
    assert get_added_content_summary(ansible_repo.to_dict()) == {"ansible.collection_mark": 1}

    # Unmark the collection version
    body = {"content_units": [collection_url], "value": "testable"}
    monitor_task(ansible_repo_api_client.unmark(ansible_repo.pulp_href, body).task)

    # Refresh the repo version
    ansible_repo = ansible_repo_api_client.read(ansible_repo.pulp_href)
    # ensure the repo version incremented
    assert ansible_repo.latest_version_href.endswith("/3/")
    # Ensure mark is removed from repo contents
    assert get_removed_content_summary(ansible_repo.to_dict()) == {"ansible.collection_mark": 1}


@pytest.fixture
def distro_serving_one_marked_one_unmarked_collection(
    build_and_upload_collection,
    ansible_repo,
    ansible_repo_api_client,
    ansible_distribution_factory,
    monitor_task,
):
    """Create a distro serving two collections, one marked, one unmarked."""
    collections = []
    for i in range(2):
        _, collection_url = build_and_upload_collection()
        collections.append(collection_url)

    body = {"add_content_units": collections}
    monitor_task(ansible_repo_api_client.modify(ansible_repo.pulp_href, body).task)

    body = {"content_units": collections[:1], "value": "marked-on-sync-test"}
    monitor_task(ansible_repo_api_client.mark(ansible_repo.pulp_href, body).task)

    return ansible_distribution_factory(ansible_repo)


def test_sync_marks(
    ansible_repo_factory,
    distro_serving_one_marked_one_unmarked_collection,
    ansible_remote_collection_api_client,
    gen_object_with_cleanup,
    ansible_repo_api_client,
    monitor_task,
):
    """Test that marks are also synced."""
    distro = distro_serving_one_marked_one_unmarked_collection
    new_repo = ansible_repo_factory()

    # Create Remote
    body = gen_ansible_remote(distro.client_url, include_pulp_auth=True)
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL(remote=remote.pulp_href)
    sync_response = ansible_repo_api_client.sync(new_repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)
    repo = ansible_repo_api_client.read(new_repo.pulp_href)

    content_response = get_content(repo.to_dict())
    assert len(content_response["ansible.collection_version"]) == 2
    assert len(content_response["ansible.collection_mark"]) == 1
