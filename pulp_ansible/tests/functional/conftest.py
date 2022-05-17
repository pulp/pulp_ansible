import uuid

import pytest

from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulpcore.client.pulp_ansible import (
    ApiClient,
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
def ansible_repo(ansible_repo_api_client, gen_object_with_cleanup):
    """Creates an Ansible Repository and deletes it at test cleanup time."""
    return gen_object_with_cleanup(ansible_repo_api_client, gen_repo())


@pytest.fixture
def gen_ansible_distribution(ansible_distro_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution and auto-deletes them at test cleanup time."""

    def _gen_ansible_distribution(ansible_repo):
        distro_data = gen_distribution(repository=ansible_repo.pulp_href)
        return gen_object_with_cleanup(ansible_distro_api_client, distro_data)

    yield _gen_ansible_distribution


@pytest.fixture
def gen_ansible_collection_remote(ansible_remote_collection_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Collection Remote with auto-deletion after the test run."""

    def _gen_ansible_collection_remote(**kwargs):
        kwargs.update({"name": str(uuid.uuid4())})
        return gen_object_with_cleanup(ansible_remote_collection_api_client, kwargs)

    yield _gen_ansible_collection_remote
