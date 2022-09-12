import uuid

import pytest

from orionutils.generator import build_collection
from pulp_smash.pulp3.utils import gen_distribution, gen_repo
from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_ansible import (
    AnsibleCollectionsApi,
    AnsibleRepositorySyncURL,
    ApiClient,
    ContentCollectionSignaturesApi,
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RepositoriesAnsibleApi,
    RepositoriesAnsibleVersionsApi,
    RemotesCollectionApi,
    RemotesGitApi,
    RemotesRoleApi,
    PulpAnsibleApiV3PluginAnsibleClientConfigurationApi,
    PulpAnsibleDefaultApiV3PluginAnsibleClientConfigurationApi,
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
def ansible_client_configuration_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return PulpAnsibleApiV3PluginAnsibleClientConfigurationApi(ansible_bindings_client)


@pytest.fixture
def ansible_client_default_configuration_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return PulpAnsibleDefaultApiV3PluginAnsibleClientConfigurationApi(ansible_bindings_client)


@pytest.fixture
def ansible_collection_signatures_client(ansible_bindings_client):
    """Provides the Ansible Collection Signatures API client object."""
    return ContentCollectionSignaturesApi(ansible_bindings_client)


@pytest.fixture
def ansible_repo_api_client(ansible_bindings_client):
    """Provides the Ansible Repository API client object."""
    return RepositoriesAnsibleApi(ansible_bindings_client)


@pytest.fixture
def ansible_repo_version_api_client(ansible_bindings_client):
    """Provides the Ansible Repository Version API client object."""
    return RepositoriesAnsibleVersionsApi(ansible_bindings_client)


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


@pytest.fixture
def ansible_remote_role_api_client(ansible_bindings_client):
    """Provides the Ansible Role Remotes API client object."""
    return RemotesRoleApi(ansible_bindings_client)


@pytest.fixture
def ansible_remote_git_api_client(ansible_bindings_client):
    """Provides the Ansible Git Remotes API client object."""
    return RemotesGitApi(ansible_bindings_client)


@pytest.fixture
def galaxy_v3_collection_versions_api_client(ansible_bindings_client):
    """Provides the Galaxy V3 Collection Versions API client object."""
    return PulpAnsibleApiV3CollectionsVersionsApi(ansible_bindings_client)


# Object Generation Fixtures


@pytest.fixture
def ansible_repo(ansible_repo_factory):
    """Creates an Ansible Repository and deletes it at test cleanup time."""
    return ansible_repo_factory()


@pytest.fixture
def ansible_repo_factory(ansible_repo_api_client, gen_object_with_cleanup):
    """A factory that creates an Ansible Repository and deletes it at test cleanup time."""

    def _ansible_repo_factory(**kwargs):
        body = gen_repo()
        body.update(kwargs)
        return gen_object_with_cleanup(ansible_repo_api_client, body)

    return _ansible_repo_factory


@pytest.fixture
def ansible_sync_factory(ansible_repo_api_client, ansible_repo_factory):
    """A factory to perform a sync on an Ansible Repository and return its updated data."""

    def _sync(ansible_repo=None, **kwargs):
        body = AnsibleRepositorySyncURL(**kwargs)
        if ansible_repo is None:
            ansible_repo = ansible_repo_factory()
        monitor_task(ansible_repo_api_client.sync(ansible_repo.pulp_href, body).task)
        return ansible_repo_api_client.read(ansible_repo.pulp_href)

    return _sync


@pytest.fixture
def ansible_distribution_factory(ansible_distro_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution with auto-cleanup."""

    def _ansible_distribution_factory(ansible_repo):
        distro_data = gen_distribution(repository=ansible_repo.pulp_href)
        return gen_object_with_cleanup(ansible_distro_api_client, distro_data)

    return _ansible_distribution_factory


@pytest.fixture
def ansible_collection_remote_factory(
    ansible_remote_collection_api_client, gen_object_with_cleanup
):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_collection_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_remote_collection_api_client, kwargs)

    return _ansible_collection_remote_factory


@pytest.fixture
def ansible_git_remote_factory(ansible_remote_git_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Git Remote with auto-cleanup."""

    def _ansible_git_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_remote_git_api_client, kwargs)

    return _ansible_git_remote_factory


@pytest.fixture
def build_and_upload_collection(ansible_collections_api_client):
    """A factory to locally create, build, and upload a collection."""

    def _build_and_upload_collection():
        collection = build_collection("skeleton")
        response = ansible_collections_api_client.upload_collection(collection.filename)
        task = monitor_task(response.task)
        return collection, task.created_resources[0]

    return _build_and_upload_collection
