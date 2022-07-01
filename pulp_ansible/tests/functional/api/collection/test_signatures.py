"""Tests functionality around Collection-Version Signatures."""
import tarfile

import pytest

from pulp_smash.pulp3.bindings import monitor_task, PulpTaskError
from pulp_smash.pulp3.utils import get_content_summary

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    gen_distribution,
    get_content,
)
from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL


@pytest.mark.pulp_on_localhost
def test_upload_then_sign_then_try_to_upload_duplicate_signature(
    build_and_upload_collection,
    ansible_collections_api_client,
    ansible_repo_api_client,
    ansible_repo,
    ascii_armored_detached_signing_service,
    tmp_path,
    sign_with_ascii_armored_detached_signing_service,
    ansible_collection_signatures_client,
):
    """Test server signing of collections, and that a duplicate signature can't be uploaded."""
    collection, collection_url = build_and_upload_collection()

    # Add it to a repo version
    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_repo_api_client.modify(ansible_repo.pulp_href, body).task)
    ansible_repo = ansible_repo_api_client.read(ansible_repo.pulp_href)

    # Assert the content was added correctly
    assert ansible_repo.latest_version_href.endswith("/1/")
    assert get_content_summary(ansible_repo.to_dict()) == {"ansible.collection_version": 1}

    # Ask Pulp to sign the collection
    body = {
        "content_units": [collection_url],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_repo_api_client.sign(ansible_repo.pulp_href, body).task)
    ansible_repo = ansible_repo_api_client.read(ansible_repo.pulp_href)

    # Assert a new repo version with signatures was created
    assert ansible_repo.latest_version_href.endswith("/2/")
    content_summary_dict = {"ansible.collection_signature": 1, "ansible.collection_version": 1}
    assert get_content_summary(ansible_repo.to_dict()) == content_summary_dict

    # Extract MANIFEST.json
    with tarfile.open(collection.filename, mode="r") as tar:
        filename = tmp_path / "MANIFEST.json"
        tar.extract("MANIFEST.json", path=tmp_path)

    # Locally sign the collection
    signing_script_response = sign_with_ascii_armored_detached_signing_service(filename)
    signature = signing_script_response["signature"]

    # Check that locally produced signature can't be uploaded
    with pytest.raises(PulpTaskError):
        task = ansible_collection_signatures_client.create(
            signed_collection=collection_url, file=signature
        )
        monitor_task(task.task)


@pytest.mark.pulp_on_localhost
def test_sign_locally_then_upload_signature(
    build_and_upload_collection,
    sign_with_ascii_armored_detached_signing_service,
    tmp_path,
    ansible_collections_api_client,
    ansible_collection_signatures_client,
    ansible_repo_factory,
    pulp_trusted_public_key_fingerprint,
    pulp_trusted_public_key,
):
    """Test uploading a locally produced Collection Signature."""
    repository = ansible_repo_factory(gpgkey=pulp_trusted_public_key)
    collection, collection_url = build_and_upload_collection()

    # Extract MANIFEST.json
    with tarfile.open(collection.filename, mode="r") as tar:
        filename = tmp_path / "MANIFEST.json"
        tar.extract("MANIFEST.json", path=tmp_path)

    # Locally sign the collection
    signing_script_response = sign_with_ascii_armored_detached_signing_service(filename)
    signature_file = signing_script_response["signature"]

    # Signature upload
    task = ansible_collection_signatures_client.create(
        signed_collection=collection_url, file=signature_file, repository=repository.pulp_href
    )
    signature_href = next(
        (
            item
            for item in monitor_task(task.task).created_resources
            if "content/ansible/collection_signatures/" in item
        )
    )
    assert signature_href is not None
    signature = ansible_collection_signatures_client.read(signature_href)
    assert signature.pubkey_fingerprint == pulp_trusted_public_key_fingerprint

    # Upload another collection that won't be signed
    another_collection, another_collection_url = build_and_upload_collection()

    # Check that invalid signatures can't be uploaded
    with pytest.raises(Exception):
        task = ansible_collection_signatures_client.create(
            signed_collection=another_collection_url,
            file=signature,
            repository=repository.pulp_href,
        )
        monitor_task(task.task)


@pytest.mark.parallel
def test_collection_signatures_immutable(ansible_collection_signatures_client):
    """Test the API doesn't provide an update or partial_update for a Collection Signature objs."""
    with pytest.raises(AttributeError):
        ansible_collection_signatures_client.update

    with pytest.raises(AttributeError):
        ansible_collection_signatures_client.partial_update


@pytest.mark.parallel
def test_collection_signatures_no_deletion(ansible_collection_signatures_client):
    """Test the API doesn't provide a delete for a Collection Signature obj."""
    with pytest.raises(AttributeError):
        ansible_collection_signatures_client.delete


# Tests for syncing Collection Signatures


@pytest.fixture
def distro_serving_one_signed_one_unsigned_collection(
    build_and_upload_collection,
    ascii_armored_detached_signing_service,
    ansible_repo,
    ansible_repo_api_client,
    ansible_distro_api_client,
):
    """Create a distro serving two collections, one signed, one unsigned."""
    collections = []
    for i in range(2):
        _, collection_url = build_and_upload_collection()
        collections.append(collection_url)

    body = {"add_content_units": collections}
    monitor_task(ansible_repo_api_client.modify(ansible_repo.pulp_href, body).task)

    body = {
        "content_units": collections[:1],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_repo_api_client.sign(ansible_repo.pulp_href, body).task)

    body = gen_distribution(repository=ansible_repo.pulp_href)
    distro_href = monitor_task(ansible_distro_api_client.create(body).task).created_resources[0]
    return ansible_distro_api_client.read(distro_href)


@pytest.mark.pulp_on_localhost
def test_sync_signatures(
    ansible_repo_factory,
    distro_serving_one_signed_one_unsigned_collection,
    ansible_remote_collection_api_client,
    gen_object_with_cleanup,
    ansible_repo_api_client,
):
    """Test that signatures are also synced."""
    distro = distro_serving_one_signed_one_unsigned_collection
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
    assert len(content_response["ansible.collection_signature"]) == 1


@pytest.mark.pulp_on_localhost
def test_sync_signatures_only(
    ansible_repo_factory,
    distro_serving_one_signed_one_unsigned_collection,
    ansible_remote_collection_api_client,
    ansible_repo_api_client,
    gen_object_with_cleanup,
):
    """Test that only collections with a signatures are synced when specified."""
    distro = distro_serving_one_signed_one_unsigned_collection
    new_repo = ansible_repo_factory()

    # Create Remote
    body = gen_ansible_remote(distro.client_url, signed_only=True, include_pulp_auth=True)
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, body)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL(remote=remote.pulp_href)
    sync_response = ansible_repo_api_client.sync(new_repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)
    repo = ansible_repo_api_client.read(new_repo.pulp_href)

    content_response = get_content(repo.to_dict())
    assert len(content_response["ansible.collection_version"]) == 1
    assert len(content_response["ansible.collection_signature"]) == 1
