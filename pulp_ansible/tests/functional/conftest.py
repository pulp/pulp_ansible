import uuid
import pytest
import numpy as np
from PIL import Image
import time

from orionutils.generator import build_collection, randstr

from pulpcore.client.pulp_ansible import (
    AnsibleCollectionsApi,
    AnsibleRepositorySyncURL,
    ApiClient,
    ContentCollectionDeprecationsApi,
    ContentCollectionMarksApi,
    ContentCollectionSignaturesApi,
    ContentCollectionVersionsApi,
    ContentNamespacesApi,
    ContentRolesApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RepositoriesAnsibleApi,
    RepositoriesAnsibleVersionsApi,
    RemotesCollectionApi,
    RemotesGitApi,
    RemotesRoleApi,
    PulpAnsibleApiV3CollectionsApi,
    PulpAnsibleApiV3NamespacesApi,
    PulpAnsibleApiV3PluginAnsibleClientConfigurationApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
    PulpAnsibleDefaultApiV3PluginAnsibleClientConfigurationApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
    PulpAnsibleApiV3PluginAnsibleContentNamespacesApi,
    PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi,
    PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
)

from pulp_ansible.tests.functional.constants import ANSIBLE_FIXTURE_URL


# Bindings API Fixtures


@pytest.fixture(scope="session")
def ansible_bindings_client(_api_client_set, bindings_cfg):
    """Provides the Ansible bindings client object."""
    api_client = ApiClient(bindings_cfg)
    _api_client_set.add(api_client)
    yield api_client
    _api_client_set.remove(api_client)


@pytest.fixture(scope="session")
def ansible_collections_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return AnsibleCollectionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_client_configuration_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return PulpAnsibleApiV3PluginAnsibleClientConfigurationApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_client_default_configuration_api_client(ansible_bindings_client):
    """Provides the Ansible Collections API client object."""
    return PulpAnsibleDefaultApiV3PluginAnsibleClientConfigurationApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_collection_signatures_client(ansible_bindings_client):
    """Provides the Ansible Collection Signatures API client object."""
    return ContentCollectionSignaturesApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_collection_mark_client(ansible_bindings_client):
    """Provides the Ansible Collection Marks API client object."""
    return ContentCollectionMarksApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_repo_api_client(ansible_bindings_client):
    """Provides the Ansible Repository API client object."""
    return RepositoriesAnsibleApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_repo_version_api_client(ansible_bindings_client):
    """Provides the Ansible Repository Version API client object."""
    return RepositoriesAnsibleVersionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_distro_api_client(ansible_bindings_client):
    """Provides the Ansible Distribution API client object."""
    return DistributionsAnsibleApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_collection_deprecations_api_client(ansible_bindings_client):
    """Provides the Ansible Deprecations API client object."""
    return ContentCollectionDeprecationsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_collection_version_api_client(ansible_bindings_client):
    """Provides the Ansible Content Collection Version API client object."""
    return ContentCollectionVersionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_remote_collection_api_client(ansible_bindings_client):
    """Provides the Ansible Collection Remotes API client object."""
    return RemotesCollectionApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_remote_role_api_client(ansible_bindings_client):
    """Provides the Ansible Role Remotes API client object."""
    return RemotesRoleApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_remote_git_api_client(ansible_bindings_client):
    """Provides the Ansible Git Remotes API client object."""
    return RemotesGitApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_namespaces_api_client(ansible_bindings_client):
    """Provides the Ansible Content Namespaces API client object."""
    return ContentNamespacesApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def ansible_roles_api_client(ansible_bindings_client):
    """Provides the Ansible Content Roles API client object."""
    return ContentRolesApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_namespaces_api_client(ansible_bindings_client):
    """Provides the *deprecated* Galaxy V3 Namespace API client object."""
    return PulpAnsibleApiV3NamespacesApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_content_collection_index_api(ansible_bindings_client):
    """Provides the Galaxy V3 Collections Index API client object."""
    return PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_plugin_namespaces_api_client(ansible_bindings_client):
    """Provides the Galaxy V3 Namespace API client object."""
    return PulpAnsibleApiV3PluginAnsibleContentNamespacesApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_collection_versions_api_client(ansible_bindings_client):
    """Provides the *deprecated* Galaxy V3 Collection Versions API client object."""
    return PulpAnsibleApiV3CollectionsVersionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_collections_api_client(ansible_bindings_client):
    """Provides the *deprecated* Galaxy V3 Collections API client object."""
    return PulpAnsibleApiV3CollectionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_content_collections_index_api_client(ansible_bindings_client):
    """Provides the Galaxy V3 Collection API client object."""
    return PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_content_collections_index_versions_api_client(ansible_bindings_client):
    """Provides the Galaxy V3 Collection Versions API client object."""
    return PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi(ansible_bindings_client)


@pytest.fixture(scope="session")
def galaxy_v3_default_search_api_client(ansible_bindings_client):
    """Provides the Galaxy V3 Search API client object."""
    return PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi(ansible_bindings_client)


# Object Generation Fixtures


@pytest.fixture
def ansible_repo(ansible_repo_factory):
    """Creates an Ansible Repository and deletes it at test cleanup time."""
    return ansible_repo_factory()


@pytest.fixture(scope="class")
def ansible_repo_factory(ansible_repo_api_client, gen_object_with_cleanup):
    """A factory that creates an Ansible Repository and deletes it at test cleanup time."""

    def _ansible_repo_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_repo_api_client, kwargs)

    return _ansible_repo_factory


@pytest.fixture(scope="class")
def ansible_sync_factory(ansible_repo_api_client, ansible_repo_factory, monitor_task):
    """A factory to perform a sync on an Ansible Repository and return its updated data."""

    def _sync(ansible_repo=None, **kwargs):
        body = AnsibleRepositorySyncURL(**kwargs)
        if ansible_repo is None:
            ansible_repo = ansible_repo_factory()
        monitor_task(ansible_repo_api_client.sync(ansible_repo.pulp_href, body).task)
        return ansible_repo_api_client.read(ansible_repo.pulp_href)

    return _sync


@pytest.fixture(scope="class")
def ansible_distribution_factory(ansible_distro_api_client, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution with auto-cleanup."""

    def _ansible_distribution_factory(repository=None, **kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        kwargs.setdefault("base_path", str(uuid.uuid4()))
        if repository:
            kwargs.setdefault("repository", repository.pulp_href)
        return gen_object_with_cleanup(ansible_distro_api_client, kwargs)

    return _ansible_distribution_factory


@pytest.fixture(scope="class")
def ansible_role_remote_factory(
    bindings_cfg, ansible_remote_role_api_client, gen_object_with_cleanup
):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_role_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        kwargs.setdefault("url", ANSIBLE_FIXTURE_URL)
        if kwargs.pop("include_pulp_auth", False):
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        return gen_object_with_cleanup(ansible_remote_role_api_client, kwargs)

    return _ansible_role_remote_factory


@pytest.fixture(scope="class")
def ansible_collection_remote_factory(
    bindings_cfg, ansible_remote_collection_api_client, gen_object_with_cleanup
):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_collection_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        if kwargs.pop("include_pulp_auth", False):
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        return gen_object_with_cleanup(ansible_remote_collection_api_client, kwargs)

    return _ansible_collection_remote_factory


@pytest.fixture(scope="class")
def ansible_git_remote_factory(
    bindings_cfg, ansible_remote_git_api_client, gen_object_with_cleanup
):
    """A factory to generate an Ansible Git Remote with auto-cleanup."""

    def _ansible_git_remote_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        if kwargs.pop("include_pulp_auth", False):
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        return gen_object_with_cleanup(ansible_remote_git_api_client, kwargs)

    return _ansible_git_remote_factory


@pytest.fixture
def build_and_upload_collection(ansible_collection_version_api_client, monitor_task):
    """A factory to locally create, build, and upload a collection."""

    def _build_and_upload_collection(ansible_repo=None, **kwargs):
        collection = build_collection("skeleton", **kwargs)
        body = {"file": collection.filename}
        if ansible_repo:
            body["repository"] = ansible_repo.pulp_href
        response = ansible_collection_version_api_client.create(**body)
        task = monitor_task(response.task)
        collection_href = [
            href for href in task.created_resources if "content/ansible/collection_versions" in href
        ]
        return collection, collection_href[0]

    return _build_and_upload_collection


@pytest.fixture
def ansible_dir_factory(tmp_path, bindings_cfg):
    """A factory to create a local ansible.cfg file with authentication"""

    def _ansible_dir_factory(server):
        username = bindings_cfg.username
        password = bindings_cfg.password

        ansible_cfg = (
            "[galaxy]\nserver_list = pulp_ansible\n\n"
            "[galaxy_server.pulp_ansible]\n"
            f"url = {server}\n"
        )

        if username is not None and password is not None:
            ansible_cfg += f"username = {username}\npassword = {password}\n"

        cfg_file = tmp_path / "ansible.cfg"
        cfg_file.write_text(ansible_cfg, encoding="UTF_8")
        return tmp_path

    return _ansible_dir_factory


@pytest.fixture
def random_image_factory(tmp_path):
    """Factory to produce a random 100x100 image."""

    def _random_image():
        imarray = np.random.rand(100, 100, 3) * 255
        im = Image.fromarray(imarray.astype("uint8")).convert("RGBA")
        path = tmp_path / f"{randstr()}.png"
        im.save(path)
        return path

    return _random_image


# Utility fixtures


@pytest.fixture(scope="session")
def wait_tasks(tasks_api_client):
    """Polls the Task API until all tasks for a resource are in a completed state."""

    def _wait_tasks(resource):
        pending_tasks = tasks_api_client.list(
            state__in=["running", "waiting"], reserved_resources=resource
        )
        while pending_tasks.count:
            time.sleep(1)
            pending_tasks = tasks_api_client.list(
                state__in=["running", "waiting"], reserved_resources=resource
            )

    return _wait_tasks
