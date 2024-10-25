import uuid
import pytest
import numpy as np
import subprocess
import time
import yaml
from types import SimpleNamespace

from pulpcore.tests.functional.utils import BindingsNamespace
from pulp_ansible.tests.functional.constants import ANSIBLE_FIXTURE_URL
from pulp_ansible.tests.functional.utils import randstr


# Bindings API Fixtures


@pytest.fixture(scope="session")
def ansible_bindings(_api_client_set, bindings_cfg):
    """
    A namespace providing preconfigured pulp_ansible api clients.

    e.g. `ansible_bindings.RepositoriesAnsibleApi.list()`.
    """
    from pulpcore.client import pulp_ansible as bindings_module

    api_client = bindings_module.ApiClient(bindings_cfg)
    _api_client_set.add(api_client)
    yield BindingsNamespace(bindings_module, api_client)
    _api_client_set.remove(api_client)


# Object Generation Fixtures


@pytest.fixture
def ansible_repo(ansible_repository_factory):
    """Creates an Ansible Repository and deletes it at test cleanup time."""
    return ansible_repository_factory()


@pytest.fixture(scope="class")
def ansible_repository_factory(ansible_bindings, gen_object_with_cleanup):
    """A factory that creates an Ansible Repository and deletes it at test cleanup time."""

    def _ansible_repository_factory(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(ansible_bindings.RepositoriesAnsibleApi, kwargs)

    return _ansible_repository_factory


ansible_repo_factory = ansible_repository_factory


@pytest.fixture(scope="class")
def ansible_sync_factory(ansible_bindings, ansible_repo_factory, monitor_task):
    """A factory to perform a sync on an Ansible Repository and return its updated data."""

    def _sync(ansible_repo=None, **kwargs):
        body = ansible_bindings.module.AnsibleRepositorySyncURL(**kwargs)
        if ansible_repo is None:
            ansible_repo = ansible_repo_factory()
        monitor_task(
            ansible_bindings.RepositoriesAnsibleApi.sync(ansible_repo.pulp_href, body).task
        )
        return ansible_bindings.RepositoriesAnsibleApi.read(ansible_repo.pulp_href)

    return _sync


@pytest.fixture(scope="class")
def ansible_distribution_factory(ansible_bindings, gen_object_with_cleanup):
    """A factory to generate an Ansible Distribution with auto-cleanup."""

    def _ansible_distribution_factory(repository=None, **kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        kwargs.setdefault("base_path", str(uuid.uuid4()))
        if repository:
            kwargs["repository"] = repository.pulp_href
        return gen_object_with_cleanup(ansible_bindings.DistributionsAnsibleApi, kwargs)

    return _ansible_distribution_factory


@pytest.fixture(scope="class")
def ansible_role_remote_factory(bindings_cfg, ansible_bindings, gen_object_with_cleanup):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_role_remote_factory(include_pulp_auth=False, **kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        kwargs.setdefault("url", ANSIBLE_FIXTURE_URL)
        if include_pulp_auth:
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        return gen_object_with_cleanup(ansible_bindings.RemotesRoleApi, kwargs)

    return _ansible_role_remote_factory


@pytest.fixture(scope="class")
def ansible_collection_remote_factory(bindings_cfg, ansible_bindings, gen_object_with_cleanup):
    """A factory to generate an Ansible Collection Remote with auto-cleanup."""

    def _ansible_collection_remote_factory(include_pulp_auth=False, **kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        if include_pulp_auth:
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        # Ratelimiting, because our tests hit galaxy pretty hard.
        kwargs["rate_limit"] = 5

        return gen_object_with_cleanup(ansible_bindings.RemotesCollectionApi, kwargs)

    return _ansible_collection_remote_factory


@pytest.fixture(scope="class")
def ansible_git_remote_factory(bindings_cfg, ansible_bindings, gen_object_with_cleanup):
    """A factory to generate an Ansible Git Remote with auto-cleanup."""

    def _ansible_git_remote_factory(include_pulp_auth=False, **kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        if include_pulp_auth:
            kwargs["username"] = bindings_cfg.username
            kwargs["password"] = bindings_cfg.password
        return gen_object_with_cleanup(ansible_bindings.RemotesGitApi, kwargs)

    return _ansible_git_remote_factory


@pytest.fixture(scope="session")
def ansible_collection_factory(tmp_path_factory):
    def _collection_factory(config=None):
        config = {} if config is None else config.copy()
        tmpdir = tmp_path_factory.mktemp("collection")
        namespace = config.setdefault("namespace", randstr())
        name = config.setdefault("name", randstr())
        config.setdefault("version", "1.0.0")

        src_path = tmpdir / namespace / name

        # Template the collection
        subprocess.run(f"ansible-galaxy collection init {namespace}.{name}", shell=True, cwd=tmpdir)

        # Adjust the template
        (src_path / "meta" / "runtime.yml").write_text('requires_ansible: ">=2.13"\n')
        (src_path / "README.md").write_text("# title\ncollection docs\n")
        galaxy_yaml = yaml.safe_load((src_path / "galaxy.yml").read_text())
        galaxy_yaml.update(config)
        (src_path / "galaxy.yml").write_text(yaml.safe_dump(galaxy_yaml))

        # Build the collection artifact
        build_proc = subprocess.run(
            "ansible-galaxy collection build .",
            shell=True,
            cwd=src_path,
            stdout=subprocess.PIPE,
            check=True,
        )
        filename = build_proc.stdout.decode("utf-8").strip().split()[-1]

        return SimpleNamespace(filename=filename, **config)

    return _collection_factory


@pytest.fixture(scope="class")
def build_and_upload_collection(ansible_bindings, monitor_task, ansible_collection_factory):
    """A factory to locally create, build, and upload a collection."""

    def _build_and_upload_collection(ansible_repo=None, **kwargs):
        collection = ansible_collection_factory(**kwargs)
        body = {"file": collection.filename}
        if ansible_repo:
            body["repository"] = ansible_repo.pulp_href
        response = ansible_bindings.ContentCollectionVersionsApi.create(**body)
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


@pytest.fixture(scope="session")
def random_image_factory(tmp_path_factory):
    """Factory to produce a random 100x100 image."""
    from PIL import Image

    def _random_image():
        imarray = np.random.rand(100, 100, 3) * 255
        im = Image.fromarray(imarray.astype("uint8")).convert("RGBA")
        path = tmp_path_factory.mktemp("images") / f"{randstr()}.png"
        im.save(path)
        return path

    return _random_image


# Utility fixtures


@pytest.fixture()
def skip_on_galaxy(pulp_versions):
    if "galaxy" in pulp_versions:
        pytest.skip("This test is not desigend to run on galaxy installations.")


@pytest.fixture(scope="session")
def wait_tasks(pulpcore_bindings):
    """Polls the Task API until all tasks for a resource are in a completed state."""

    def _wait_tasks(resource):
        pending_tasks = pulpcore_bindings.TasksApi.list(
            state__in=["running", "waiting"], reserved_resources=resource
        )
        while pending_tasks.count:
            time.sleep(1)
            pending_tasks = pulpcore_bindings.TasksApi.list(
                state__in=["running", "waiting"], reserved_resources=resource
            )

    return _wait_tasks
