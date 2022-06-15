import uuid

import pytest

from orionutils.generator import build_collection
from pulp_smash.pulp3.utils import gen_distribution, gen_repo
from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_ansible import (
    AnsibleCollectionsApi,
    ApiClient,
    ContentCollectionSignaturesApi,
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    RepositoriesAnsibleApi,
    RemotesCollectionApi,
)


# Bindings API Fixtures


@pytest.fixture
def ansible_bindings_client(cid, bindings_cfg):
    """Provides the Ansible bindings client object."""
    api_client = ApiClient(bindings_cfg)
    api_client.default_headers["Correlation-ID"] = cid
    return api_client


@pytest.fixture
def ansible_collections_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return AnsibleCollectionsApi(ansible_bindings_client)


@pytest.fixture
def ansible_collection_signatures_client(ansible_bindings_client):
    """Provides the Ansible Collection Signatures API client object."""
    return ContentCollectionSignaturesApi(ansible_bindings_client)


@pytest.fixture
def ansible_repo_api_client(ansible_bindings_client):
    """Provides the Ansible Repository API client object."""
    return RepositoriesAnsibleApi(ansible_bindings_client)


@pytest.fixture
def ansible_distro_api_client(ansible_bindings_client):
    """Provides the Ansible Distribution API client object."""
    return DistributionsAnsibleApi(ansible_bindings_client)


@pytest.fixture
def ansible_collection_version_api_client(ansible_bindings_client):
    """Provides the Ansible Content Collection Version API client object."""
    return ContentCollectionVersionsApi(ansible_bindings_client)


@pytest.fixture
def ansible_remote_collection_api_client(ansible_bindings_client):
    """Provides the Ansible Collection Remotes API client object."""
    return RemotesCollectionApi(ansible_bindings_client)


# Object Generation Fixtures


@pytest.fixture
def ansible_repo(ansible_repo_factory):
    """Creates an Ansible Repository and deletes it at test cleanup time."""
    return ansible_repo_factory()


@pytest.fixture
def ansible_repo_factory(ansible_repo_api_client, gen_object_with_cleanup):
    """A factory that creates an Ansible Repository and deletes it at test cleanup time."""

    def _ansible_repo_factory():
        return gen_object_with_cleanup(ansible_repo_api_client, gen_repo())

    return _ansible_repo_factory


@pytest.fixture
def gen_ansible_distribution(ansible_distro_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution with auto-cleanup."""

    def _gen_ansible_distribution(ansible_repo):
        distro_data = gen_distribution(repository=ansible_repo.pulp_href)
        return gen_object_with_cleanup(ansible_distro_api_client, distro_data)

    yield _gen_ansible_distribution


@pytest.fixture
def gen_ansible_collection_remote(ansible_remote_collection_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _gen_ansible_collection_remote(**kwargs):
        kwargs.update({"name": str(uuid.uuid4())})
        return gen_object_with_cleanup(ansible_remote_collection_api_client, kwargs)

    yield _gen_ansible_collection_remote


@pytest.fixture
def build_and_upload_collection(ansible_collections_api_client):
    """A factory to locally create, build, and upload a collection."""

    def _build_and_upload_collection():
        collection = build_collection("skeleton")
        response = ansible_collections_api_client.upload_collection(collection.filename)
        task = monitor_task(response.task)
        return collection, task.created_resources[0]

    return _build_and_upload_collection
