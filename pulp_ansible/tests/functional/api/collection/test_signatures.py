"""Tests functionality around Collection-Version Signatures."""

import tarfile

import pysequoia
import pytest

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL
from pulpcore.tests.functional.utils import PulpTaskError

from pulp_ansible.tests.functional.utils import content_counts

# Signing key variants exercised by the parametrized tests below: traditional
# (v4) crypto, OpenPGP v6 (RFC9580), and the post-quantum ML-DSA cipher suites.
# All verification runs through pulpcore's `gpg_verify` (backed by pysequoia).
KEY_PARAMS = [
    pytest.param({}, id="v4-traditional"),
    pytest.param({"profile": pysequoia.Profile.RFC9580}, id="v6-ed25519"),
    pytest.param(
        {
            "profile": pysequoia.Profile.RFC9580,
            "cipher_suite": pysequoia.CipherSuite.MLDSA65_Ed25519,
        },
        id="pqc-mldsa65-ed25519",
    ),
    pytest.param(
        {
            "profile": pysequoia.Profile.RFC9580,
            "cipher_suite": pysequoia.CipherSuite.MLDSA87_Ed448,
        },
        id="pqc-mldsa87-ed448",
    ),
]


def test_upload_then_sign_then_try_to_upload_duplicate_signature(
    ansible_bindings,
    build_and_upload_collection,
    ansible_repo_factory,
    ascii_armored_detached_signing_service,
    tmp_path,
    sign_with_ascii_armored_detached_signing_service,
    monitor_task,
):
    """Test server signing of collections, and that a duplicate signature can't be uploaded."""
    repository = ansible_repo_factory()
    collection, collection_url = build_and_upload_collection()

    # Add it to a repo version
    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, body).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    # Assert the content was added correctly
    assert repository.latest_version_href.endswith("/1/")

    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version) == {"ansible.collection_version": 1}

    # Ask Pulp to sign the collection
    body = {
        "content_units": [collection_url],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(repository.pulp_href, body).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    # Assert a new repo version with signatures was created
    assert repository.latest_version_href.endswith("/2/")
    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version) == {
        "ansible.collection_signature": 1,
        "ansible.collection_version": 1,
    }

    # Extract MANIFEST.json
    with tarfile.open(collection.filename, mode="r") as tar:
        filename = tmp_path / "MANIFEST.json"
        tar.extract("MANIFEST.json", path=tmp_path)

    # Locally sign the collection
    signing_script_response = sign_with_ascii_armored_detached_signing_service(filename)
    signature = signing_script_response["signature"]

    # Check that locally produced signature can't be uploaded
    with pytest.raises(PulpTaskError):
        task = ansible_bindings.ContentCollectionSignaturesApi.create(
            signed_collection=collection_url, file=signature
        )
        monitor_task(task.task)


def test_sign_locally_then_upload_signature(
    ansible_bindings,
    build_and_upload_collection,
    sign_with_ascii_armored_detached_signing_service,
    tmp_path,
    ansible_repo_factory,
    pulp_trusted_public_key_fingerprint,
    pulp_trusted_public_key,
    monitor_task,
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
    task = ansible_bindings.ContentCollectionSignaturesApi.create(
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
    signature = ansible_bindings.ContentCollectionSignaturesApi.read(signature_href)
    assert signature.pubkey_fingerprint == pulp_trusted_public_key_fingerprint

    # Upload another collection that won't be signed
    another_collection, another_collection_url = build_and_upload_collection()

    # Check that invalid signatures can't be uploaded
    with pytest.raises(Exception):
        task = ansible_bindings.ContentCollectionSignaturesApi.create(
            signed_collection=another_collection_url,
            file=signature,
            repository=repository.pulp_href,
        )
        monitor_task(task.task)


@pytest.mark.parallel
def test_collection_signatures_immutable(ansible_bindings):
    """Test the API doesn't provide an update or partial_update for a Collection Signature objs."""
    with pytest.raises(AttributeError):
        ansible_bindings.ContentCollectionSignaturesApi.update

    with pytest.raises(AttributeError):
        ansible_bindings.ContentCollectionSignaturesApi.partial_update


@pytest.mark.parallel
def test_collection_signatures_no_deletion(ansible_bindings):
    """Test the API doesn't provide a delete for a Collection Signature obj."""
    with pytest.raises(AttributeError):
        ansible_bindings.ContentCollectionSignaturesApi.delete


# Tests for syncing Collection Signatures


@pytest.fixture
def distro_serving_one_signed_one_unsigned_collection(
    ansible_bindings,
    build_and_upload_collection,
    ascii_armored_detached_signing_service,
    ansible_repo_factory,
    ansible_distribution_factory,
    monitor_task,
):
    """Create a distro serving two collections, one signed, one unsigned."""
    repository = ansible_repo_factory()
    collections = []
    for i in range(2):
        _, collection_url = build_and_upload_collection()
        collections.append(collection_url)

    body = {"add_content_units": collections}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, body).task)

    body = {
        "content_units": collections[:1],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(repository.pulp_href, body).task)

    return ansible_distribution_factory(repository=repository)


def test_sync_signatures(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    distro_serving_one_signed_one_unsigned_collection,
    monitor_task,
):
    """Test that signatures are also synced."""
    distro = distro_serving_one_signed_one_unsigned_collection
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
        "ansible.collection_signature": 1,
    }


def test_sync_signatures_only(
    ansible_bindings,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    distro_serving_one_signed_one_unsigned_collection,
    monitor_task,
):
    """Test that only collections with a signatures are synced when specified."""
    distro = distro_serving_one_signed_one_unsigned_collection
    repository = ansible_repo_factory()

    # Create Remote
    remote = ansible_collection_remote_factory(
        url=distro.client_url, signed_only=True, include_pulp_auth=True
    )

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
        "ansible.collection_version": 1,
        "ansible.collection_signature": 1,
    }


# Tests covering traditional, OpenPGP v6, and post-quantum (ML-DSA) signatures


@pytest.mark.parametrize("generate_kwargs", KEY_PARAMS)
def test_upload_signature_with_key_type(
    ansible_bindings,
    build_and_upload_collection,
    ansible_repo_factory,
    tmp_path,
    monitor_task,
    generate_kwargs,
):
    """A locally-produced signature is verified against the repo's gpgkey and accepted.

    Also asserts that a signature made with a non-trusted key is rejected. Runs for
    traditional (v4), OpenPGP v6, and post-quantum ML-DSA keys.
    """
    tsk = pysequoia.Tsk.generate("Pulp Test <pulp-test@example.com>", **generate_kwargs)
    public_key = str(tsk.extract_certificate())
    repository = ansible_repo_factory(gpgkey=public_key)
    collection, collection_url = build_and_upload_collection()

    # Extract `MANIFEST.json` from a built collection
    with tarfile.open(collection.filename, mode="r") as tar:
        tar.extract("MANIFEST.json", path=tmp_path)
    manifest_path = tmp_path / "MANIFEST.json"
    signature_file = tmp_path / "MANIFEST.json.asc"
    with open(manifest_path, "rb") as f:
        sig = pysequoia.sign(tsk.signer(), f.read(), mode=pysequoia.SignatureMode.DETACHED)
    with open(signature_file, "wb") as f:
        f.write(sig)

    task = ansible_bindings.ContentCollectionSignaturesApi.create(
        signed_collection=collection_url,
        file=str(signature_file),
        repository=repository.pulp_href,
    )
    signature_href = next(
        item
        for item in monitor_task(task.task).created_resources
        if "content/ansible/collection_signatures/" in item
    )
    signature = ansible_bindings.ContentCollectionSignaturesApi.read(signature_href)
    assert len(signature.pubkey_fingerprint) == 64

    # A signature made with a different (untrusted) key must be rejected.
    other_tsk = pysequoia.Tsk.generate("Pulp Test <pulp-test@example.com>", **generate_kwargs)
    bad_signature_file = tmp_path / "MANIFEST.json.bad.asc"
    with open(manifest_path, "rb") as f:
        sig = pysequoia.sign(other_tsk.signer(), f.read(), mode=pysequoia.SignatureMode.DETACHED)
    with open(bad_signature_file, "wb") as f:
        f.write(sig)
    another_collection, another_collection_url = build_and_upload_collection()
    with pytest.raises(PulpTaskError):
        task = ansible_bindings.ContentCollectionSignaturesApi.create(
            signed_collection=another_collection_url,
            file=str(bad_signature_file),
            repository=repository.pulp_href,
        )
        monitor_task(task.task)


@pytest.mark.parametrize(
    "signing_service_fixture",
    [
        "ascii_armored_detached_signing_service",
        "sq_ascii_armored_detached_signing_service",
        "sq_pqc_ascii_armored_detached_signing_service",
    ],
)
def test_sign_with_signing_service_key_type(
    ansible_bindings,
    build_and_upload_collection,
    ansible_repo_factory,
    monitor_task,
    request,
    signing_service_fixture,
):
    """Pulp signs a collection server-side with GPG, v6, and PQC signing services."""
    signing_service = request.getfixturevalue(signing_service_fixture)
    repository = ansible_repo_factory()
    _collection, collection_url = build_and_upload_collection()

    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, body).task)

    body = {
        "content_units": [collection_url],
        "signing_service": signing_service.pulp_href,
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(repository.pulp_href, body).task)
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)

    repository_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )
    assert content_counts(repository_version) == {
        "ansible.collection_signature": 1,
        "ansible.collection_version": 1,
    }

    signatures = ansible_bindings.ContentCollectionSignaturesApi.list(
        signed_collection=collection_url
    ).results
    assert len(signatures) == 1
    # The signature records the fingerprint of the signing service's key.
    assert signatures[0].pubkey_fingerprint == signing_service.pubkey_fingerprint
