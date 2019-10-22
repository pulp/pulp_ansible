# coding=utf-8
"""Tests related to upload of collections."""
import hashlib
import logging
import re
import unittest
from urllib.parse import urljoin

import pytest
import requests

from pulp_smash import api, config
from pulp_smash.pulp3.utils import delete_orphans
from pulp_smash.utils import http_get
from requests.exceptions import HTTPError

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_FILE_NAME,
    ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL,
    COLLECTION_METADATA,
    GALAXY_ANSIBLE_BASE_URL_V3,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from orionutils.generator import build_collection


logger = logging.getLogger(__name__)


repo = "automation-hub"


def upload_handler(client, response):
    """Handle responses to collection upload by fetching and returning the task data."""

    response.raise_for_status()
    logger.debug("response status: %s", response.status_code)
    if response.status_code == 204:
        return response
    api._handle_202(client._cfg, response, client.pulp_host)
    if response.request.method == "POST":
        task_url = response.json()['task']
        task = client.get(task_url)
        return task
    else:
        return response.json()


@pytest.fixture(scope='session')
def artifact():
    artifact = build_collection('skeleton')
    return artifact


@pytest.fixture(scope='session')
def collection_upload(pulp_client, artifact):
    # Publish a new collection
    cfg = config.get_config()
    UPLOAD_PATH = urljoin(cfg.get_base_url(), f"api/{repo}/v3/artifacts/collections/")
    collection = {
        "file": (ANSIBLE_COLLECTION_FILE_NAME, open(artifact.filename, 'rb'))
    }

    response = pulp_client.using_handler(upload_handler).post(UPLOAD_PATH, files=collection)
    return response


@pytest.fixture(scope='session')
def collection_detail(collection_upload, pulp_client, artifact):
    url = f"/api/{repo}/v3/collections/{artifact.namespace}/{artifact.name}/"
    response = pulp_client.using_handler(api.json_handler).get(url)
    return response


@pytest.fixture(scope='session')
def pulp_client():
    cfg = config.get_config()
    delete_orphans(cfg)
    client = api.Client(cfg)
    headers = cfg.custom['headers']
    client.request_kwargs.setdefault('headers', {}).update(headers)
    return client


@pytest.fixture(scope='session')
def known_collection():
    collection_content = http_get(ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL)

    collection = {"file": (ANSIBLE_COLLECTION_FILE_NAME, collection_content)}
    collection_sha256 = hashlib.sha256(collection_content).hexdigest()
    return collection

    
def test_collection_upload(collection_upload):
    """Upload a new collection.

    Uploads a newly generated collection and validates the resulting collection version details.
    """
    
    # Validate the upload response
    assert collection_upload['error'] == None
    assert re.match(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', collection_upload['id'])
    assert collection_upload['messages'][0]['level'] == 'INFO'
    assert collection_upload['messages'][0]['message'] == 'Content search - Analyzing collection structure'

    assert collection_upload['state'] == 'completed'

    assert 'updated_at' in collection_upload
    assert 'started_at' in collection_upload
    assert 'created_at' in collection_upload
    assert 'finished_at' in collection_upload

    for key, value in collection_upload.items():
        if key in COLLECTION_METADATA.keys():
            assert COLLECTION_METADATA[key] == value, collection_upload


def test_collection_detail(artifact, collection_detail):
    """Test collection detail resulting from a successful upload of one version.

    Includes information of the most current version.
    """

    url = f"/api/{repo}/v3/collections/{artifact.namespace}/{artifact.name}/"

    # Detail Endpoint
    assert 'created_at' in collection_detail
    assert 'updated_at' in collection_detail

    assert collection_detail['deprecated'] == False
    assert collection_detail['href'] == url
    assert collection_detail['namespace'] == artifact.namespace
    assert collection_detail['name'] == artifact.name
    assert collection_detail['highest_version']['version'] == '1.0.0'


def test_collection_version_list(artifact, pulp_client, collection_detail):
    """???

    ???
    """

    # Version List Endpoint
    versions = pulp_client.using_handler(api.json_handler).get(collection_detail['versions_url'])
    assert versions['count'] == 1
    version = versions['results'][0]

    assert version['version'] == '1.0.0'
    assert version['is_certified'] == False
    assert version['href'] == collection_detail['highest_version']['href']


def test_collection_version(artifact, pulp_client, collection_detail):
    """Test collection version endpoint.

    Each collection version details a specific uploaded artifact for the collection.
    """

    # Version Endpoint
    version = pulp_client.using_handler(api.json_handler).get(collection_detail['highest_version']['href'])
    
    assert version['name'] == artifact.name
    assert version['namespace'] == {'name': artifact.namespace}
    assert version['version'] == '1.0.0'
    assert version['is_certified'] == False

    tarball = open(artifact.filename, 'rb').read()
    assert version['artifact']['sha256'] == hashlib.sha256(tarball).hexdigest()
    assert version['artifact']['size'] == len(tarball)
    
    # assert version['artifact']['filename'] == artifact.filename

    assert 'updated_at' in version
    assert 'created_at' in version

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


def test_collection_download(artifact, pulp_client, collection_detail):
    """Test collection download URL.

    Should require authentication and redirect to a download location.
    """

    version = pulp_client.using_handler(api.json_handler).get(collection_detail['highest_version']['href'])

    # Artifact Download Endoint
    url = version['download_url']

    tarball = open(artifact.filename, 'rb').read()

    c = pulp_client.using_handler(api.echo_handler)
    f = c.get(url)
    assert f.status_code == 200, (url, f.request.headers)
    assert f.content == tarball


def test_collection_upload_repeat(pulp_client, known_collection):
    """Upload a duplicate collection.

    Should fail, because of the conflict of collection name and version.
    """

    cfg = config.get_config()
    UPLOAD_PATH = urljoin(cfg.get_base_url(), f"api/{repo}/v3/artifacts/collections/")

    with pytest.raises(HTTPError) as ctx:
        response = pulp_client.post(UPLOAD_PATH, files=known_collection)

        assert ctx.exception.response.json()["errors"][0] == {
            'status': '400',
            'code': 'invalid',
            'title': 'Invalid input.',
            'detail': 'Artifact already exists.',
        }

        for key, value in collection_upload.items():
            if key in COLLECTION_METADATA.keys():
                assert COLLECTION_METADATA[key] == value, response

        collection_sha256 = hashlib.sha256(known_collection['files'][1]).hexdigest()
        assert response["sha256"] == collection_sha256, response

