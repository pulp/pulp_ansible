import pytest
import hashlib
import requests
import random
import string

import numpy as np
from PIL import Image

from pulpcore.client.pulp_ansible.exceptions import ApiException, ApiValueError
from pulp_ansible.tests.functional.utils import iterate_all


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


def test_invalid_namespace_names(
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    global_ansible_namespaces_api_client
):
    """Test that users can't create namespaces with invalid names."""
    repo, distro = ansible_repo_and_distro_factory()
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    invalid_names = [
        "",
        "_hello_world",
        "123345",
        "2cool4school",
        "x",
        "xy",
        "my-namespace-name",
        "my.namespace.name",
        "hello!",
    ]

    for name in invalid_names:
        try:
            global_ansible_namespaces_api_client.create({"name": name})
        except ApiException as e:
            assert "name" in e.body
        except ApiValueError as e:
            assert "name" in str(e)
        else:
            assert not f"User was able to create global namespace with invalid name {name}"

        try:
            galaxy_v3_plugin_namespaces_api_client.create(
                name=name, **kwargs
            )
        except ApiException as e:
            assert "name" in e.body
        except ApiValueError as e:
            assert "name" in str(e)
        else:
            assert not f"User was able to create namespace metadata with invalid name {name}"


def test_namespace_groups(
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    groups_api_client,
    monitor_task,
):
    """
    Test that the legacy groups field works.
    """

    group_1 = random_string()
    group_2 = random_string()

    groups_api_client.create({"name": group_1})
    groups_api_client.create({"name": group_2})

    repo, distro = ansible_repo_and_distro_factory()
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    # Create namespace with no groups
    name = random_string()
    result = galaxy_v3_plugin_namespaces_api_client.create(
        name=name, **kwargs
    )
    monitor_task(result.task)

    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert v3_namespace.groups == []

    group_1_mapping = {
        "name": group_1,
        "object_roles": ["ansible.namespace_owner"],
    }

    group_2_mapping = {
        "name": group_2,
        "object_roles": ["ansible.namespace_owner"],
    }

    # Create namespace with groups
    name = random_string()
    result = galaxy_v3_plugin_namespaces_api_client.create(
        name=name, groups=[group_1_mapping, ], **kwargs
    )
    monitor_task(result.task)
    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert {x.name for x in v3_namespace.groups} == {group_1}

    # Verify partial update doesn't remove groups
    result = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, description="foo", **kwargs
    )
    monitor_task(result.task)
    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert {x.name for x in v3_namespace.groups} == {group_1}

    # Add an extra group
    result = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, groups=[group_1_mapping, group_2_mapping,], **kwargs
    )
    monitor_task(result.task)
    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert {x.name for x in v3_namespace.groups} == {group_1, group_2}

    # Remove groups
    result = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, groups=[], **kwargs
    )
    monitor_task(result.task)
    v3_namespace = galaxy_v3_plugin_namespaces_api_client.read(name=name, **kwargs)
    assert v3_namespace.groups == []


def test_namespace_metadata_search(
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    monitor_task,
    ansible_namespace_search_api_client,
    ansible_repo_api_client,
    ansible_distro_api_client
):
    """
    Test that the namespaces search API is returning all the distributed namespace
    metadata content.
    """
    repo1, distro1 = ansible_repo_and_distro_factory()
    repo2, distro2 = ansible_repo_and_distro_factory()

    repo1_namespaces = [random_string() for x in range(3)]
    repo2_namespaces = [random_string() for x in range(3)]
    shared_ns = [random_string() for x in range(3)]

    def _tupleify(namespaces, repos):
        content_set = set()

        for ns in namespaces:
            for r in repos:
                content_set.add((r.name, ns))

        return content_set

    # populate two repositories with a set of shared and unique namespaces
    for name in repo1_namespaces + shared_ns:
        kwargs = {"path": distro1.base_path, "distro_base_path": distro1.base_path}
        result = galaxy_v3_plugin_namespaces_api_client.create(
            name=name, **kwargs
        )
        monitor_task(result.task)

    for name in repo2_namespaces + shared_ns:
        kwargs = {"path": distro2.base_path, "distro_base_path": distro2.base_path}
        result = galaxy_v3_plugin_namespaces_api_client.create(
            name=name, **kwargs
        )
        monitor_task(result.task)

    repo1_set = _tupleify(shared_ns + repo1_namespaces, [repo1])
    repo2_set = _tupleify(shared_ns + repo2_namespaces, [repo2])

    # test that the namespaces from every repo with a distribution are returned
    search_results = set()

    for ns in iterate_all(ansible_namespace_search_api_client.list):
        search_results.add((ns.repository.name, ns.metadata.name))
        assert ns.in_latest_repo_version
        assert not ns.in_old_repo_version

    assert search_results == repo1_set | repo2_set

    # add a new distro pointing to a specific repository version of the first repo
    task = ansible_distro_api_client.create({
        "base_path": random_string(),
        "name": random_string(),
        "repository_version": ansible_repo_api_client.read(repo1.pulp_href).latest_version_href
    })

    new_distro_href = monitor_task(task.task).created_resources[0]

    # The number of results should be unchanged
    assert len(search_results) == ansible_namespace_search_api_client.list().count

    # Contents of repo1 should be marked as in latest and old repo version
    for ns in iterate_all(ansible_namespace_search_api_client.list, repository_name=repo1.name):
        assert ns.in_latest_repo_version
        assert not ns.in_old_repo_version

    # Remove a namespace from the first repo
    removed_namespace = repo1_namespaces.pop()
    repo1_set = _tupleify(shared_ns + repo1_namespaces, [repo1])

    kwargs = {"path": distro1.base_path, "distro_base_path": distro1.base_path}
    monitor_task(
        galaxy_v3_plugin_namespaces_api_client.delete(name=removed_namespace, **kwargs).task)

    # Contents of repo1 should be marked as in latest and old repo version
    for ns in iterate_all(ansible_namespace_search_api_client.list, repository_name=repo1.name):
        if ns.metadata.name != removed_namespace:
            assert ns.in_latest_repo_version
            assert not ns.in_old_repo_version
        else:
            # namespace that was removed from latest version should no longer be marked
            # as in latest
            assert not ns.in_latest_repo_version
            assert ns.in_old_repo_version

    # Since there's still a distro pointing to the old repo version, the number of
    # results should be unchanged
    old_count = ansible_namespace_search_api_client.list().count
    assert len(search_results) == old_count

    # Delete the new distro
    monitor_task(ansible_distro_api_client.delete(new_distro_href).task)

    # The removed namespace should no longer appear in the search now that the distro that it
    # was in has been deleted
    search_results = {
        (x.repository.name, x.metadata.name) for x in iterate_all(
            ansible_namespace_search_api_client.list)
    }

    assert search_results == repo1_set | repo2_set
    assert ansible_namespace_search_api_client.list().count == old_count - 1

    # Delete distro1
    monitor_task(ansible_distro_api_client.delete(distro1.pulp_href).task)

    # The content in distro1 should be removed from the search results
    search_results = {
        (x.repository.name, x.metadata.name) for x in iterate_all(
            ansible_namespace_search_api_client.list)
    }

    assert search_results == repo2_set


def test_global_namespaces_latest_metadata(
    global_ansible_namespaces_api_client,
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    monitor_task,
):
    """
    Test that the latest metadata field is updated on the global namespace api
    """

    repo, distro = ansible_repo_and_distro_factory()
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    # Create namespace with v3 api
    name = random_string()
    description = "ns 1"
    result = galaxy_v3_plugin_namespaces_api_client.create(
        name=name, description=description, **kwargs
    )
    monitor_task(result.task)

    # test that the latest_namespace field is updated on the global namespace api
    g_ns = global_ansible_namespaces_api_client.list(name=name).results[0]
    assert g_ns.latest_metadata.description == description

    description = "ns 2"
    result = galaxy_v3_plugin_namespaces_api_client.partial_update(
        name=name, description=description, **kwargs
    )
    monitor_task(result.task)

    g_ns = global_ansible_namespaces_api_client.list(name=name).results[0]
    assert g_ns.latest_metadata.description == description

    # verify namespaces with metadata can't be deleted
    try:
        global_ansible_namespaces_api_client.delete(g_ns.pulp_href)
    except ApiException as e:
        assert "cannot be deleted" in e.body
    else:
        assert not "User's should not be able to delete namespaces with namespace metadata"


def test_global_namespaces_latest_crud(
    global_ansible_namespaces_api_client,
    ansible_repo_and_distro_factory,
    galaxy_v3_plugin_namespaces_api_client,
    monitor_task,
    gen_user
):
    ns_owner = gen_user()

    # Create the namespace
    name = random_string()
    global_ansible_namespaces_api_client.create({"name": name})
    g_ns = global_ansible_namespaces_api_client.list(name=name).results[0]
    assert g_ns.name == name

    # test my permissions filter
    with ns_owner:
        assert global_ansible_namespaces_api_client.list(
            name=name, my_permissions="ansible.change_ansiblenamespace").count == 0

    global_ansible_namespaces_api_client.add_role(
        g_ns.pulp_href,
        {
            "users": [ns_owner.user.username, ],
            "role": "ansible.namespace_owner"
        }
    )

    # test my permissions filter
    with ns_owner:
        results = global_ansible_namespaces_api_client.list(
            name=name, my_permissions="ansible.change_ansiblenamespace")

        assert results.count == 1
        assert "ansible.change_ansiblenamespace" in results.results[0].my_permissions

    global_ansible_namespaces_api_client.delete(g_ns.pulp_href)
    assert global_ansible_namespaces_api_client.list(name=name).count == 0


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
    result = galaxy_v3_plugin_namespaces_api_client.create(
        name=name, description="hello", company="Testing Co.", links=links, **kwargs
    )
    task_result = monitor_task(result.task)

    assert len(task_result.created_resources) == 1
    # namespace_href = result.created_resources[1]
    # assert "content/ansible/namespaces/" in namespace_href
    namespace_href = result.pulp_href

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
    updated_namespace_href = task.pulp_href
    result = monitor_task(task.task)
    assert len(result.created_resources) == 1
    repo_version = result.created_resources[0]
    assert repo_version[-2] == "2"

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
    updated2_namespace_href = task.pulp_href
    result = monitor_task(task.task)
    assert len(result.created_resources) == 1
    repo_version = result.created_resources[0]
    assert repo_version[-2] == "3"
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

    assert len(result.created_resources) == 1
    namespace_href = task.pulp_href

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
        ns = galaxy_v3_plugin_namespaces_api_client.create(
            name=namespace, avatar=avatar_path, **kwargs1
        )
        monitor_task(ns.task)
        collections.append(collection)
        namespaces[namespace] = ns.pulp_href

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
