from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    get_added_content_summary,
    get_content_summary,
    get_removed_content_summary,
)


def test_add_mark_to_collection_version(
    build_and_upload_collection,
    ansible_repo_api_client,
    ansible_repo,
    ansible_collection_mark_client,
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
