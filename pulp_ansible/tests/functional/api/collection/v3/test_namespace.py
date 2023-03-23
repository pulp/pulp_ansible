import pytest
import hashlib
import requests
import random
import string

import numpy as np
from PIL import Image


def random_string(n=10):
    """Create a random lower_case + digits string."""
    a = random.choice(string.ascii_lowercase)
    return a + "".join(random.choices(string.ascii_lowercase + string.digits, k=n - 1))


@pytest.fixture
def ansible_repo_and_distro_factory(ansible_repo_factory, ansible_distribution_factory):
    """Factory to produce a repo and distro."""

    def _factory(repo_kwargs=None):
        repo_kwargs = repo_kwargs or {}
        ansible_repo = ansible_repo_factory(**repo_kwargs)
        distro = ansible_distribution_factory(ansible_repo)
        return ansible_repo, distro

    return _factory


@pytest.fixture
def random_image_factory(tmp_path):
    """Factory to produce a random 100x100 image."""

    def _random_image():
        imarray = np.random.rand(100, 100, 3) * 255
        im = Image.fromarray(imarray.astype("uint8")).convert("RGBA")
        path = tmp_path / f"{random_string()}.png"
        im.save(path)
        return path

    return _random_image


def test_crud_namespaces(
    ansible_repo_and_distro_factory,
    ansible_namespaces_api_client,
    galaxy_v3_plugin_namespaces_api_client,
    monitor_task,
):
    """Test Basic Creating, Reading, Updating and 'Deleting' operations on Namespaces."""
    repo, distro = ansible_repo_and_distro_factory()
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    links = [
        {"name": "link1", "url": "http://galaxy.ansible.com"},
        {"name": "link2", "url": "http://begta-galaxy.ansible.com"},
    ]

    # Test Basic Creation
    name = random_string()
    task = galaxy_v3_plugin_namespaces_api_client.create(
        name=name, description="hello", company="Testing Co.", links=links, **kwargs
    )
    result = monitor_task(task.task)

    assert len(result.created_resources) == 2
    namespace_href = result.created_resources[1]
    assert "content/ansible/namespaces/" in namespace_href

    def _link_to_dict(resp):
        return {x.name: x.url for x in resp}

    link_comparison = {x["name"]: x["url"] for x in links}

    # Test Reading Namespace from Pulp API
    namespace = ansible_namespaces_api_client.read(namespace_href)
    assert namespace.name == name
    assert namespace.company == "Testing Co."
    assert namespace.description == "hello"
    assert namespace.metadata_sha256 != ""
    assert namespace.avatar_url is None
    assert _link_to_dict(namespace.links) == link_comparison

    # Test Reading Namespace from Galaxy API
    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert v3_namespace.pulp_href == namespace.pulp_href
    assert v3_namespace.name == name
    assert v3_namespace.company == "Testing Co."
    assert v3_namespace.description == "hello"
    assert v3_namespace.metadata_sha256 != ""
    assert v3_namespace.avatar_url is None
    assert _link_to_dict(v3_namespace.links) == link_comparison

    v3_list = galaxy_v3_plugin_namespaces_api_client.list(**kwargs)
    assert v3_list.count == 1

    # Test Update Namespace (Creates a new Namespace w/ updated metadata)
    task = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, description="hey!", **kwargs
    )
    result = monitor_task(task.task)
    assert len(result.created_resources) == 2
    repo_version = result.created_resources[0]
    assert repo_version[-2] == "2"
    updated_namespace_href = result.created_resources[1]
    assert updated_namespace_href != namespace_href

    updated_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert updated_namespace.pulp_href == updated_namespace_href
    assert updated_namespace.name == name
    assert updated_namespace.company == "Testing Co."
    assert updated_namespace.description == "hey!"
    assert updated_namespace.metadata_sha256 != v3_namespace.metadata_sha256

    # Test Updating Namespace back to original description brings back original object
    task = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, description="hello", links=links, **kwargs
    )
    result = monitor_task(task.task)
    assert len(result.created_resources) == 2
    repo_version = result.created_resources[0]
    assert repo_version[-2] == "3"
    updated2_namespace_href = result.created_resources[1]
    assert updated2_namespace_href == namespace_href

    # Test 'Deleting' a Namespace (Namespace are removed from Galaxy API, but are still in Pulp)
    task = galaxy_v3_plugin_namespaces_api_client.delete(name=name, **kwargs)
    result = monitor_task(task.task)
    assert len(result.created_resources) == 1
    repo_version = result.created_resources[0]
    assert repo_version[-2] == "4"

    namespaces = ansible_namespaces_api_client.list(name=name)
    assert namespaces.count == 2

    v3_namespaces = galaxy_v3_plugin_namespaces_api_client.list(**kwargs)
    assert v3_namespaces.count == 0


def test_namespace_avatar(
    ansible_repo_and_distro_factory,
    ansible_namespaces_api_client,
    galaxy_v3_plugin_namespaces_api_client,
    random_image_factory,
    monitor_task,
):
    """Test creating a Namespace w/ an Avatar & downloading the image from the Galaxy API."""
    repo, distro = ansible_repo_and_distro_factory()
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    name = random_string()
    avatar_path = random_image_factory()
    with open(avatar_path, "rb") as av:
        avatar_sha256 = hashlib.sha256(av.read()).hexdigest()

    task = galaxy_v3_plugin_namespaces_api_client.create(name=name, avatar=avatar_path, **kwargs)
    result = monitor_task(task.task)

    assert len(result.created_resources) == 2
    namespace_href = result.created_resources[1]

    namespace = ansible_namespaces_api_client.read(namespace_href)
    assert namespace.avatar_sha256 == avatar_sha256
    assert namespace.avatar_url.endswith(f"{namespace_href}avatar/")

    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert v3_namespace.pulp_href == namespace_href
    assert v3_namespace.avatar_sha256 == avatar_sha256
    assert v3_namespace.avatar_url.endswith(f"{namespace_href}avatar/")

    r = requests.get(v3_namespace.avatar_url)
    assert r.status_code == 200
    downloaded_sha256 = hashlib.sha256(r.content).hexdigest()
    assert downloaded_sha256 == v3_namespace.avatar_sha256


def test_namespace_syncing(
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    build_and_upload_collection,
    random_image_factory,
    monitor_task,
    ansible_sync_factory,
    ansible_collection_remote_factory,
    pulp_admin_user,
):
    """Test syncing a Collection w/ a Namespace also syncs the Namespace."""
    # Set up first Repo to have 3 Collections and 3 Namespaces
    repo1, distro1 = ansible_repo_and_distro_factory()
    kwargs1 = {"path": distro1.base_path, "distro_base_path": distro1.base_path}

    collections = []
    namespaces = {}
    for i in range(3):
        namespace = random_string()
        collection, _ = build_and_upload_collection(repo1, config={"namespace": namespace})
        avatar_path = random_image_factory()
        task = galaxy_v3_plugin_namespaces_api_client.create(
            name=namespace, avatar=avatar_path, **kwargs1
        )
        result = monitor_task(task.task)
        collections.append(collection)
        namespaces[namespace] = result.created_resources[-1]

    # Set up second Repo and sync 2 Collections from first Repo
    repo2, distro2 = ansible_repo_and_distro_factory()
    kwargs2 = {"path": distro2.base_path, "distro_base_path": distro2.base_path}
    collections_string = "\n  - ".join((f"{c.namespace}.{c.name}" for c in collections[0:2]))
    requirements = f"collections:\n  - {collections_string}"
    remote = ansible_collection_remote_factory(
        url=distro1.client_url,
        requirements_file=requirements,
        username=pulp_admin_user.username,
        password=pulp_admin_user.password,
    )

    ansible_sync_factory(ansible_repo=repo2, remote=remote.pulp_href)
    # 2 Namespaces should have also been synced
    synced_namespaces = galaxy_v3_plugin_namespaces_api_client.list(**kwargs2)
    assert synced_namespaces.count == 2
    for namespace in synced_namespaces.results:
        assert namespace.name in namespaces
        assert namespaces[namespace.name] == namespace.pulp_href
