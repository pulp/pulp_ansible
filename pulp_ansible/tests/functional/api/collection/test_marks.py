import pytest
from pulp_ansible.tests.functional.utils import content_counts
from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL


def test_add_mark_to_collection_version(
    ansible_bindings,
    ansible_repo_factory,
    build_and_upload_collection,
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
    repository = ansible_repo_factory()
    collection, collection_url = build_and_upload_collection()

    # add it to a repo version
    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, body).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    # assert the content was added correctly
    assert repository.latest_version_href.endswith("/1/")

    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )

    assert content_counts(repository_version) == {"ansible.collection_version": 1}

    # Add a mark to the collection version
    body = {"content_units": [collection_url], "value": "testable"}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.mark(repository.pulp_href, body).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    # assert the repo version incremented
    assert repository.latest_version_href.endswith("/2/")
    # Ensure mark with value "testable" is present on the marks
    marks = ansible_bindings.ContentCollectionMarksApi.list(
        marked_collection=collection_url
    ).results
    assert len(marks) == 1
    assert marks[0].value == "testable"
    assert marks[0].marked_collection == collection_url

    # Ensure mark is added to the repo
    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version, "added") == {"ansible.collection_mark": 1}

    # Unmark the collection version
    body = {"content_units": [collection_url], "value": "testable"}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.unmark(repository.pulp_href, body).task)

    # Refresh the repo version
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    # ensure the repo version incremented
    assert repository.latest_version_href.endswith("/3/")
    # Ensure mark is removed from repo contents
    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version, "removed") == {"ansible.collection_mark": 1}


@pytest.fixture
def distro_serving_one_marked_one_unmarked_collection(
    ansible_bindings,
    ansible_repo_factory,
    build_and_upload_collection,
    ansible_distribution_factory,
    monitor_task,
):
    """Create a distro serving two collections, one marked, one unmarked."""
    repository = ansible_repo_factory()
    collections = []
    for i in range(2):
        _, collection_url = build_and_upload_collection()
        collections.append(collection_url)

    body = {"add_content_units": collections}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, body).task)

    body = {"content_units": collections[:1], "value": "marked-on-sync-test"}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.mark(repository.pulp_href, body).task)

    return ansible_distribution_factory(repository)


def test_sync_marks(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    distro_serving_one_marked_one_unmarked_collection,
    monitor_task,
):
    """Test that marks are also synced."""
    distro = distro_serving_one_marked_one_unmarked_collection
    repository = ansible_repo_factory()

    # Create Remote
    remote = ansible_collection_remote_factory(url=distro.client_url, include_pulp_auth=True)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL(remote=remote.pulp_href)
    sync_response = ansible_bindings.RepositoriesAnsibleApi.sync(
        repository.pulp_href, repository_sync_data
    )
    monitor_task(sync_response.task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version) == {
        "ansible.collection_version": 2,
        "ansible.collection_mark": 1,
    }
