import pytest

from pulpcore.client.pulp_ansible.exceptions import ApiException

from pulp_ansible.tests.functional.utils import content_counts, randstr


def test_collection_deletion(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Test deleting an entire collection."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)
    assert collections.meta.count == 1

    task = monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        ).task
    )
    assert len(task.created_resources) == 1

    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)
    assert collections.meta.count == 0

    versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        path=distribution.base_path,
        name=collection_name,
        namespace=collection_namespace,
    )

    assert versions.meta.count == 0

    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.read(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        )

    assert exc_info.value.status == 404


def test_collection_version_deletion(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Test deleting a specific collection version."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)
    assert collections.meta.count == 1

    versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        path=distribution.base_path,
        name=collection_name,
        namespace=collection_namespace,
    )
    assert versions.meta.count == 2

    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.0",
        ).task
    )

    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.read(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.0",
        )
    assert exc_info.value.status == 404

    # Verify that the collection still exists
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)
    assert collections.meta.count == 1

    # Verify that the other versions still exist
    versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        path=distribution.base_path,
        name=collection_name,
        namespace=collection_namespace,
    )
    assert versions.meta.count == 1

    # Delete the other versions

    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.1",
        ).task
    )

    # Verify all the versions have been deleted
    versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        path=distribution.base_path,
        name=collection_name,
        namespace=collection_namespace,
    )
    assert versions.meta.count == 0

    # With all the versions deleted, verify that the collection has also
    # been deleted
    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.read(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        )
    assert exc_info.value.status == 404


def test_invalid_deletion(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Test deleting collections that are dependencies for other collections."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    dependent_collection, dependent_collection_href = build_and_upload_collection(
        repository,
        config={"dependencies": {f"{collection_namespace}.{collection_name}": "1.0.0"}},
    )

    err_msg = f"{dependent_collection.namespace}.{dependent_collection.name} 1.0.0"

    # Verify entire collection can't be deleted
    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        )

    # check error message includes collection that's blocking delete
    assert err_msg in exc_info.value.body

    # Verify specific version that's used can't be deleted
    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.0",
        )
    assert exc_info.value.status == 400

    # check error message includes collection that's blocking delete
    assert err_msg in exc_info.value.body

    # Verify non dependent version can be deleted.
    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.1",
        ).task
    )


def test_delete_deprecated_content(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Test that deprecated content is removed correctly."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    # Deprecate the collection
    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.update(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            patched_collection={"deprecated": True},
        ).task
    )

    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        ).task
    )

    # Verify that all the content is gone
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    latest_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )

    assert content_counts(latest_version) == {}


def test_delete_signed_content(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    ascii_armored_detached_signing_service,
    monitor_task,
):
    """Test that signature content is removed correctly."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    # Sign the collections
    body = {
        "content_units": [
            "*",
        ],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(repository.pulp_href, body).task)

    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
        ).task
    )

    # Verify that all the content is gone
    repository = ansible_bindings.RepositoriesAnsibleApi.read(repository.pulp_href)
    latest_version = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        repository.latest_version_href
    )

    assert content_counts(latest_version) == {}


def test_version_deletion_with_range_of_versions(
    ansible_bindings,
    ansible_distribution_factory,
    ansible_repository_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Verify collections can be deleted when another version satisfies requirements."""
    repository = ansible_repository_factory()
    distribution = ansible_distribution_factory(repository=repository)

    collection_name = randstr()
    collection_namespace = randstr()
    for version in ["1.0.0", "1.0.1"]:
        build_and_upload_collection(
            repository,
            config={"name": collection_name, "namespace": collection_namespace, "version": version},
        )

    # Create a collection that depends on any version of an existing collection
    dependent_collection, dependent_collection_href = build_and_upload_collection(
        repository,
        config={"dependencies": {f"{collection_namespace}.{collection_name}": "*"}},
    )

    # Verify the collection version can be deleted as long as there is one version
    # left that satisfies the requirements.
    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.0",
        ).task
    )

    # Verify that the last version of the collection can't be deleted

    with pytest.raises(ApiException) as exc_info:
        ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.delete(
            path=distribution.base_path,
            name=collection_name,
            namespace=collection_namespace,
            version="1.0.1",
        )

    assert exc_info.value.status == 400
