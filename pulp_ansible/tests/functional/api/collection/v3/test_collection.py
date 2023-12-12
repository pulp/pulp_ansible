"""Tests related to upload of collections."""

import hashlib
import pathlib
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import pytest
import requests


class NullAuth(requests.auth.AuthBase):
    def __call__(self, r):
        return r


class BaseURLSession(requests.Session):
    def __init__(self, base_url, *args, **kwargs):
        self.base_url = base_url
        super().__init__(*args, **kwargs)

    def request(self, method, url, **kwargs):
        return super().request(method, urljoin(self.base_url, url), **kwargs)


@pytest.fixture(scope="module")
def http_session(bindings_cfg):
    with BaseURLSession(bindings_cfg.host) as session:
        session.auth = (bindings_cfg.username, bindings_cfg.password)
        yield session


def get_galaxy_url(base, path):
    """Given an Ansible Distribution base_path and an endpoint path, construct a URL.

    Takes the expected GALAXY_API_ROOT setting of the target into consideration.
    """
    GALAXY_API_ROOT = f"/pulp_ansible/galaxy/{base}/api/"
    return urljoin(GALAXY_API_ROOT, path.lstrip("/"))


@pytest.fixture(scope="module")
def collection_artifact(ansible_collection_factory):
    """Generate a randomized collection for testing."""
    return ansible_collection_factory()


@pytest.fixture(scope="module")
def collection_artifact2(ansible_collection_factory):
    """
    Generate a second randomized collection for testing.

    This collection will have the same namespace and version, but different name.
    """
    return ansible_collection_factory()


def get_metadata_published(http_session, pulp_dist):
    """Return published datetime."""
    response = http_session.get(get_galaxy_url(pulp_dist.base_path, "/v3/"))
    response.raise_for_status()
    metadata = response.json()
    return datetime.strptime(metadata["published"], "%Y-%m-%dT%H:%M:%S.%fZ")


def upload_collection(http_session, filename, base_path):
    """Helper to upload collections to pulp_ansible/galaxy."""
    UPLOAD_PATH = get_galaxy_url(base_path, "/v3/artifacts/collections/")
    with open(filename, "rb") as fp:
        collection = {"file": fp}
        response = http_session.post(UPLOAD_PATH, files=collection)
    response.raise_for_status()
    task = response.json()["task"]
    while True:
        response = http_session.get(task)
        response.raise_for_status()
        result = response.json()
        if result["state"] == "running":
            time.sleep(1)
            continue
        if result["state"] == "completed":
            break
        raise Exception(str(result))
    return result


@pytest.fixture(scope="class")
def collection_upload(http_session, collection_artifact, pulp_dist):
    """Publish a new collection and return the processed response data."""
    published_before_upload = get_metadata_published(http_session, pulp_dist)
    response = upload_collection(http_session, collection_artifact.filename, pulp_dist.base_path)
    published_after_upload = get_metadata_published(http_session, pulp_dist)
    assert published_after_upload > published_before_upload
    return response


@pytest.fixture(scope="class")
def collection_upload2(http_session, collection_artifact2, pulp_dist):
    """Publish the second new collection and return the processed response data."""
    published_before_upload = get_metadata_published(http_session, pulp_dist)
    response = upload_collection(http_session, collection_artifact2.filename, pulp_dist.base_path)
    published_after_upload = get_metadata_published(http_session, pulp_dist)
    assert published_after_upload > published_before_upload
    return response


@pytest.fixture(scope="class")
def collection_detail(http_session, collection_upload, pulp_dist, collection_artifact):
    """Fetch and parse a collection details response from an uploaded collection."""
    url = get_galaxy_url(
        pulp_dist.base_path,
        f"/v3/collections/{collection_artifact.namespace}/{collection_artifact.name}/",
    )
    response = http_session.get(url)
    response.raise_for_status()
    return response.json()


@pytest.fixture(scope="class")
def pulp_dist(ansible_repository_factory, ansible_distribution_factory):
    """Create an Ansible Distribution to simulate the automation hub environment for testing."""
    return ansible_distribution_factory(repository=ansible_repository_factory())


class TestCollection:

    def test_collection_upload(self, collection_upload):
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

        # TODO: Add this back when namespace, name, and version are apart of the CollectionImport
        # for key, value in collection_upload.items():
        #     if key in COLLECTION_METADATA.keys():
        #         assert COLLECTION_METADATA[key] == value, collection_upload

    def test_collection_list(
        self,
        http_session,
        collection_artifact,
        collection_artifact2,
        collection_upload,
        collection_upload2,
        pulp_dist,
    ):
        """Tests the collection list endpoint after uploading both collections."""
        url = get_galaxy_url(pulp_dist.base_path, "v3/collections/")
        response = http_session.get(url)
        response.raise_for_status()
        result = response.json()

        assert result["meta"]["count"] >= 2
        present_collections = {c["href"].split("collections/")[1] for c in result["data"]}
        uploaded_collections = {
            f"index/{collection_artifact.namespace}/{collection_artifact.name}/",
            f"index/{collection_artifact2.namespace}/{collection_artifact2.name}/",
        }
        assert uploaded_collections.issubset(present_collections)

    def test_collection_detail(self, collection_artifact, collection_detail, pulp_dist):
        """Test collection detail resulting from a successful upload of one version.

        Includes information of the most current version.
        """
        url = (
            f"plugin/ansible/content/{pulp_dist.base_path}"
            f"/collections/index/{collection_artifact.namespace}/{collection_artifact.name}/"
        )

        assert not collection_detail["deprecated"]

        # Check that the URL ends with the correct path so that this test doesn't fail
        # when galaxy_ng is installed
        assert collection_detail["href"].endswith(url)
        assert collection_detail["namespace"] == collection_artifact.namespace
        assert collection_detail["name"] == collection_artifact.name
        assert collection_detail["highest_version"]["version"] == "1.0.0"
        assert collection_detail["download_count"] == 0

    def test_collection_version_list(
        self, http_session, collection_artifact, collection_detail, collection_upload2
    ):
        """Test the versions endpoint, listing the available versions of a given collection."""
        # Version List Endpoint
        response = http_session.get(collection_detail["versions_url"])
        response.raise_for_status()
        versions = response.json()
        assert versions["meta"]["count"] == 1
        version = versions["data"][0]

        assert version["version"] == "1.0.0"
        assert version["href"] == collection_detail["highest_version"]["href"]

    def test_collection_version_filter_by_q(
        self,
        ansible_bindings,
        ansible_collection_factory,
        pulp_dist,
        monitor_task,
        delete_orphans_pre,
    ):
        """Verify successive imports do not aggregate tags into search vectors."""

        def publish(new_artifact):
            body = {
                "file": new_artifact.filename,
                "expected_namespace": new_artifact.namespace,
                "expected_name": new_artifact.name,
                "expected_version": new_artifact.version,
            }
            resp = ansible_bindings.ContentCollectionVersionsApi.create(**body)
            monitor_task(resp.task)

        # make&publish 2 collections with each having unique tags
        specs = [("tag1", "ns1", "col1"), ("tag2", "ns1", "col2")]
        for spec in specs:
            cfg = {
                "namespace": spec[1],
                "name": spec[2],
                "description": "",
                "repository": f"https://github.com/{spec[1]}/{spec[2]}",
                "authors": ["jimbob"],
                "version": "1.0.0",
                "tags": [spec[0]],
            }
            this_artifact = ansible_collection_factory(config=cfg)
            publish(this_artifact)

        for spec in specs:
            resp = ansible_bindings.ContentCollectionVersionsApi.list(q=spec[0])

            # should only get the 1 cv as a result ...
            assert resp.count == 1
            assert resp.results[0].namespace == spec[1]
            assert resp.results[0].name == spec[2]

    def test_collection_version(self, http_session, collection_artifact, collection_detail):
        """Test collection version endpoint.

        Each collection version details a specific uploaded artifact for the collection.
        """
        # Version Endpoint
        response = http_session.get(collection_detail["highest_version"]["href"])
        response.raise_for_status()
        version = response.json()

        assert version["name"] == collection_artifact.name
        assert version["namespace"] == {
            "metadata_sha256": None,
            "name": collection_artifact.namespace,
        }
        assert version["version"] == "1.0.0"
        with open(collection_artifact.filename, "rb") as fp:
            tarball = fp.read()
        assert version["artifact"]["sha256"] == hashlib.sha256(tarball).hexdigest()
        assert version["artifact"]["size"] == len(tarball)

        assert version["artifact"]["filename"] == pathlib.Path(collection_artifact.filename).name

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

    def test_collection_download(
        self,
        http_session,
        collection_detail,
        collection_artifact,
    ):
        """Test collection download URL.

        Should require authentication and redirect to a download location.
        """
        response = http_session.get(collection_detail["highest_version"]["href"], auth=NullAuth())
        assert response.status_code == 401
        response = http_session.get(collection_detail["highest_version"]["href"])
        response.raise_for_status()
        version = response.json()

        # Artifact Download Endoint
        url = version["download_url"]

        with open(collection_artifact.filename, "rb") as fp:
            tarball = fp.read()

        response = http_session.get(url, auth=NullAuth())
        assert response.status_code == 401
        response = http_session.get(url)
        assert response.status_code == 200, (url, response.request.headers)
        assert response.content == tarball

    def test_collection_upload_repeat(
        self, http_session, ansible_collection_factory, pulp_dist, collection_upload
    ):
        """
        Upload a duplicate collection.
        """
        response = upload_collection(
            http_session, ansible_collection_factory().filename, pulp_dist.base_path
        )
        assert response["error"] is None
        assert response["state"] == "completed"
        assert re.match(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", response["id"]
        )
