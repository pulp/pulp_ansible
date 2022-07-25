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
    ContentRolesApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RepositoriesAnsibleApi,
    RepositoriesAnsibleVersionsApi,
    RemotesCollectionApi,
    RemotesGitApi,
    RemotesRoleApi,
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
def ansible_role_api_client(ansible_bindings_client):
    """Provides the Ansible Content Role API client object."""
    return ContentRolesApi(ansible_bindings_client)


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
def sync_repo_factory(ansible_repo_api_client):
    """A factory to perform a sync on an Ansible Repository and return its updated data."""

    def _sync(ansible_repo, **kwargs):
        body = AnsibleRepositorySyncURL(**kwargs)
        monitor_task(ansible_repo_api_client.sync(ansible_repo.pulp_href, body).task)
        return ansible_repo_api_client.read(ansible_repo.pulp_href)

    yield _sync


@pytest.fixture
def ansible_distribution_factory(ansible_distro_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution with auto-cleanup."""

    def _ansible_distribution_factory(ansible_repo):
        distro_data = gen_distribution(repository=ansible_repo.pulp_href)
        return gen_object_with_cleanup(ansible_distro_api_client, distro_data)

    yield _ansible_distribution_factory


@pytest.fixture
def ansible_collection_remote_factory(
    ansible_remote_collection_api_client, gen_object_with_cleanup
):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_collection_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_remote_collection_api_client, kwargs)

    yield _ansible_collection_remote_factory


@pytest.fixture
def ansible_git_remote_factory(ansible_remote_git_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Git Remote with auto-cleanup."""

    def _ansible_git_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_remote_git_api_client, kwargs)

    yield _ansible_git_remote_factory


@pytest.fixture
def ansible_role_remote_factory(ansible_remote_role_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Role Remote with auto-cleanup."""

    def _ansible_role_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_remote_role_api_client, kwargs)

    yield _ansible_role_remote_factory


@pytest.fixture
def build_and_upload_collection(ansible_collections_api_client):
    """A factory to locally create, build, and upload a collection."""

    def _build_and_upload_collection():
        collection = build_collection("skeleton")
        response = ansible_collections_api_client.upload_collection(collection.filename)
        task = monitor_task(response.task)
        return collection, task.created_resources[0]

    return _build_and_upload_collection


@pytest.fixture
def sync_and_count_factory(
    ansible_collection_remote_factory,
    ansible_git_remote_factory,
    ansible_role_remote_factory,
    ansible_repo_factory,
    sync_repo_factory,
    ansible_collection_version_api_client,
    ansible_role_api_client,
):
    """A fixture to build a helper fixture to perform a sync and check the count of Collections."""

    def _sync_and_count_builder(remote_type):
        # This could be made even more generic to apply to all plugins
        content_client = ansible_collection_version_api_client
        if remote_type == "collection":
            remote_factory = ansible_collection_remote_factory
        elif remote_type == "git":
            remote_factory = ansible_git_remote_factory
        elif remote_type == "role":
            remote_factory = ansible_role_remote_factory
            content_client = ansible_role_api_client
        else:
            raise NotImplementedError

        def _sync_and_count(remote_body, repo=None, **sync_kwargs):
            if repo is None:
                repo = ansible_repo_factory()
            previous_latest = repo.latest_version_href
            remote = remote_factory(**remote_body)
            sync_kwargs.update({"remote": remote.pulp_href})
            repo = sync_repo_factory(repo, **sync_kwargs)
            assert repo.latest_version_href != previous_latest
            c = content_client.list(repository_version=repo.latest_version_href)
            return c.count

        return _sync_and_count

    yield _sync_and_count_builder
