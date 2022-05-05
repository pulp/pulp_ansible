"""Tests related to upload of collections."""
import hashlib
import logging
import os
import re
import shutil
from datetime import datetime
from urllib.parse import urljoin

import pytest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_distribution, gen_repo
from pulp_smash.utils import http_get

from requests.exceptions import HTTPError

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_FILE_NAME,
    ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL,
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_REPO_PATH,
    COLLECTION_METADATA,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from orionutils.generator import build_collection


logger = logging.getLogger(__name__)


def upload_handler(client, response):
    """Handle responses to collection upload by fetching and returning the task data."""
    response.raise_for_status()
    logger.debug("response status: %s", response.status_code)
    if response.status_code == 204:
        return response
    api._handle_202(client._cfg, response, client.pulp_host)
    if response.request.method == "POST":
        task_url = response.json()["task"]
        task = client.get(task_url)
        return task
    else:
        return response.json()


def get_galaxy_url(base, path):
    """Given an Ansible Distribution base_path and an endpoint path, construct a URL.

    Takes the expected GALAXY_API_ROOT setting of the target into consideration.
    """
    cfg = config.get_config()
    path = path.lstrip("/")
    GALAXY_API_ROOT = cfg.custom.get(
        "galaxy_api_root", "/pulp_ansible/galaxy/%(base_path)s/api/"
    ) % {"base_path": base}
    return urljoin(GALAXY_API_ROOT, path)


@pytest.fixture(scope="session")
def artifact():
    """Generate a randomized collection for testing."""
    # build_collection will only store one collection, so copy to new location and delete later
    artifact = build_collection("skeleton")
    artifact.filename = shutil.copy(artifact.filename, "/tmp")
    yield artifact
    os.remove(artifact.filename)


@pytest.fixture(scope="session")
def artifact2():
    """
    Generate a second randomized collection for testing.

    This collection will have the same namespace and version, but different name.
    """
    artifact2 = build_collection("skeleton")
    return artifact2


def get_metadata_published(pulp_client, pulp_dist):
    """Return published datetime."""
    metadata = pulp_client.using_handler(api.json_handler).get(
        get_galaxy_url(pulp_dist["base_path"], "/v3/")
    )
    return datetime.strptime(metadata["published"], "%Y-%m-%dT%H:%M:%S.%fZ")


@pytest.fixture(scope="session")
def collection_upload(pulp_client, artifact, pulp_dist):
    """Publish a new collection and return the processed response data."""
    UPLOAD_PATH = get_galaxy_url(pulp_dist["base_path"], "/v3/artifacts/collections/")
    published_before_upload = get_metadata_published(pulp_client, pulp_dist)
    logging.info(f"Uploading collection to '{UPLOAD_PATH}'...")
    collection = {"file": (ANSIBLE_COLLECTION_FILE_NAME, open(artifact.filename, "rb"))}

    response = pulp_client.using_handler(upload_handler).post(UPLOAD_PATH, files=collection)
    published_after_upload = get_metadata_published(pulp_client, pulp_dist)
    assert published_after_upload > published_before_upload
    return response


@pytest.fixture(scope="session")
def collection_upload2(pulp_client, artifact2, pulp_dist):
    """Publish the second new collection and return the processed response data."""
    UPLOAD_PATH = get_galaxy_url(pulp_dist["base_path"], "/v3/artifacts/collections/")
    published_before_upload = get_metadata_published(pulp_client, pulp_dist)
    logging.info(f"Uploading collection to '{UPLOAD_PATH}'...")
    collection = {"file": (open(artifact2.filename, "rb"))}

    response = pulp_client.using_handler(upload_handler).post(UPLOAD_PATH, files=collection)
    published_after_upload = get_metadata_published(pulp_client, pulp_dist)
    assert published_after_upload > published_before_upload
    return response


@pytest.fixture(scope="session")
def collection_detail(collection_upload, pulp_client, pulp_dist, artifact):
    """Fetch and parse a collection details response from an uploaded collection."""
    url = get_galaxy_url(
        pulp_dist["base_path"], f"/v3/collections/{artifact.namespace}/{artifact.name}/"
    )
    response = pulp_client.using_handler(api.json_handler).get(url)
    return response


@pytest.fixture(scope="session")
def pulp_client():
    """Create and configure a Pulp API client, including custom authentication headers."""
    cfg = config.get_config()
    client = api.Client(cfg)
    headers = cfg.custom.get("headers", None)
    if headers:
        client.request_kwargs.setdefault("headers", {}).update(headers)
    return client


@pytest.fixture(scope="session")
def pulp_repo(pulp_client):
    """Find or create a Repository to attach to the Ansible Distribution we create."""
    repos = pulp_client.get(ANSIBLE_REPO_PATH)
    if repos:
        yield repos[0]
    else:
        repo_data = gen_repo(name="automation-hub")
        repo = pulp_client.post(ANSIBLE_REPO_PATH, repo_data)
        yield repo
        pulp_client.delete(repo["pulp_href"])


@pytest.fixture(scope="session")
def pulp_dist(pulp_client, pulp_repo):
    """Create an Ansible Distribution to simulate the automation hub environment for testing."""
    dists = pulp_client.get(ANSIBLE_DISTRIBUTION_PATH + "?base_path=automation-hub")

    if len(dists) == 0:
        dist_data = gen_distribution(
            name="automation-hub", base_path="automation-hub", repository=pulp_repo["pulp_href"]
        )
        dist = pulp_client.post(ANSIBLE_DISTRIBUTION_PATH, dist_data)
        created = True
    elif len(dists) == 1:
        dist = dists[0]
        created = False
    else:
        raise ValueError("Found too many Ansible Distributions at 'automation-hub'.")
    yield dist
    if created:
        pulp_client.delete(dist["pulp_href"])


@pytest.fixture(scope="session")
def known_collection():
    """Fetch and prepare a known collection from Galaxy to use in an upload test."""
    collection_content = http_get(ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL)
    collection = {"file": (ANSIBLE_COLLECTION_FILE_NAME, collection_content)}
    return collection


def test_collection_upload(collection_upload):
    """Upload a new collection.

    Uploads a newly generated collection and validates the resulting collection version details.
    """
    # Validate the upload response
    assert collection_upload["error"] is None
    assert re.match(
        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", collection_upload["id"]
    )
    assert collection_upload["state"] == "completed"

    assert "updated_at" in collection_upload
    assert "started_at" in collection_upload
    assert "created_at" in collection_upload
    assert "finished_at" in collection_upload
    assert "messages" in collection_upload

    for key, value in collection_upload.items():
        if key in COLLECTION_METADATA.keys():
            assert COLLECTION_METADATA[key] == value, collection_upload


def test_collection_list(
    artifact, artifact2, collection_upload, collection_upload2, pulp_client, pulp_dist
):
    """Tests the collection list endpoint after uploading both collections."""
    url = get_galaxy_url(pulp_dist["base_path"], "v3/collections/")
    response = pulp_client.using_handler(api.json_handler).get(url)

    assert response["meta"]["count"] >= 2
    present_collections = {c["href"].split("collections/")[1] for c in response["data"]}
    uploaded_collections = {
        f"index/{artifact.namespace}/{artifact.name}/",
        f"index/{artifact2.namespace}/{artifact2.name}/",
    }
    assert uploaded_collections.issubset(present_collections)


def test_collection_detail(artifact, collection_detail, pulp_dist):
    """Test collection detail resulting from a successful upload of one version.

    Includes information of the most current version.
    """
    url = (
        f"plugin/ansible/content/{pulp_dist['base_path']}"
        f"/collections/index/{artifact.namespace}/{artifact.name}/"
    )

    assert not collection_detail["deprecated"]

    # Check that the URL ends with the correct path so that this test doesn't fail
    # when galaxy_ng is installed
    assert collection_detail["href"].endswith(url)
    assert collection_detail["namespace"] == artifact.namespace
    assert collection_detail["name"] == artifact.name
    assert collection_detail["highest_version"]["version"] == "1.0.0"


def test_collection_version_list(artifact, pulp_client, collection_detail, collection_upload2):
    """Test the versions endpoint, listing the available versions of a given collection."""
    # Version List Endpoint
    versions = pulp_client.using_handler(api.json_handler).get(collection_detail["versions_url"])
    assert versions["meta"]["count"] == 1
    version = versions["data"][0]

    assert version["version"] == "1.0.0"
    assert version["href"] == collection_detail["highest_version"]["href"]


def test_collection_version(artifact, pulp_client, collection_detail):
    """Test collection version endpoint.

    Each collection version details a specific uploaded artifact for the collection.
    """
    # Version Endpoint
    version = pulp_client.using_handler(api.json_handler).get(
        collection_detail["highest_version"]["href"]
    )

    assert version["name"] == artifact.name
    assert version["namespace"] == {"name": artifact.namespace}
    assert version["version"] == "1.0.0"

    tarball = open(artifact.filename, "rb").read()
    assert version["artifact"]["sha256"] == hashlib.sha256(tarball).hexdigest()
    assert version["artifact"]["size"] == len(tarball)

    # assert version['artifact']['filename'] == artifact.filename

    assert "updated_at" in version
    assert "created_at" in version

    assert "files" in version
    assert "manifest" in version
    assert "requires_ansible" in version

    #     # TODO: Test meta data
    #     # 'metadata': {'authors': ['Orion User 1'],
    #     #             'contents': [],
    #     #             'dependencies': {},
    #     #             'description': 'a collection with some deps on other collections',
    #     #             'documentation': '',
    #     #             'homepage': '',
    #     #             'issues': '',
    #     #             'license': ['GPL-3.0-or-later'],
    #     #             'repository': 'http://github.example.com/orionuser1/skeleton',
    #     #             'tags': ['collectiontest']},


@pytest.mark.skip("Blocked by open ticket: https://github.com/pulp/pulp_ansible/issues/698")
def test_collection_download(artifact, pulp_client, collection_detail):
    """Test collection download URL.

    Should require authentication and redirect to a download location.
    """
    version = pulp_client.using_handler(api.json_handler).get(
        collection_detail["highest_version"]["href"]
    )

    # Artifact Download Endoint
    url = version["download_url"]

    tarball = open(artifact.filename, "rb").read()

    c = pulp_client.using_handler(api.echo_handler)
    f = c.get(url)
    assert f.status_code == 200, (url, f.request.headers)
    assert f.content == tarball


def test_collection_upload_repeat(pulp_client, known_collection, pulp_dist):
    """Upload a duplicate collection.

    Should fail, because of the conflict of collection name and version.
    """
    cfg = config.get_config()
    url = urljoin(cfg.get_base_url(), f"api/{pulp_dist['base_path']}/v3/artifacts/collections/")

    with pytest.raises(HTTPError) as ctx:
        response = pulp_client.post(url, files=known_collection)

        assert ctx.exception.response.json()["errors"][0] == {
            "status": "400",
            "code": "invalid",
            "title": "Invalid input.",
            "detail": "Artifact already exists.",
        }

        for key, value in collection_upload.items():
            if key in COLLECTION_METADATA.keys():
                assert COLLECTION_METADATA[key] == value, response

        collection_sha256 = hashlib.sha256(known_collection["files"][1]).hexdigest()
        assert response["sha256"] == collection_sha256, response
