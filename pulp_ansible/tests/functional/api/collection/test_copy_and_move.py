import pytest
from pulp_ansible.tests.functional.utils import iterate_all


@pytest.fixture
def repo_with_kitted_out_collection(
    pulpcore_bindings,
    ansible_bindings,
    build_and_upload_collection,
    ascii_armored_detached_signing_service,
    ansible_repo,
    ansible_distribution_factory,
    monitor_task,
):
    """
    Create a repo that has a collection with all the possible associated content.

    Repo contains 3 collections. 2 are returned to be copied, one of which has all
    the content associated with it and the other of which as a mark and signature.

    Returns the repo, two collections to copy and the list of expected content
    after the copy operation happens.
    """
    collection, collection_url = build_and_upload_collection()
    _, collection_url2 = build_and_upload_collection()
    _, non_copied_collection = build_and_upload_collection()

    # add collection to repo
    body = {"add_content_units": [collection_url, collection_url2, non_copied_collection]}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(ansible_repo.pulp_href, body).task)

    # sign the collection
    body = {
        "content_units": [collection_url, collection_url2, non_copied_collection],
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(ansible_repo.pulp_href, body).task)

    # Mark the collection
    body = {
        "content_units": [collection_url, collection_url2, non_copied_collection],
        "value": "testable",
    }
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.mark(ansible_repo.pulp_href, body).task)

    # Not gonna bother adding these to the first collection
    # Create a distro for the repo
    distro = ansible_distribution_factory(repository=ansible_repo)

    # Add a namespace for the collection
    kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}
    task = ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi.create(
        name=collection.namespace, description="hello", company="Testing Co.", **kwargs
    )
    monitor_task(task.task)

    # Deprecate the collection
    task = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi.update(
        name=collection.name,
        namespace=collection.namespace,
        distro_base_path=distro.base_path,
        patched_collection={"deprecated": True},
    )
    monitor_task(task.task)

    repo = ansible_bindings.RepositoriesAnsibleApi.read(ansible_repo.pulp_href)

    expected_content = {
        "collection_versions",
        "namespaces",
        "collection_signatures",
        "collection_marks",
        "collection_deprecations",
    }

    created_content = set()
    all_content = set()
    excluded_content = {non_copied_collection}

    # get the signatures and marks from the excluded collection:
    excluded_content = excluded_content.union(
        {
            x.pulp_href
            for x in iterate_all(
                ansible_bindings.ContentCollectionSignaturesApi.list,
                signed_collection=non_copied_collection,
            )
        }
    )

    excluded_content = excluded_content.union(
        {
            x.pulp_href
            for x in iterate_all(
                ansible_bindings.ContentCollectionMarksApi.list,
                marked_collection=non_copied_collection,
            )
        }
    )

    assert len(excluded_content) >= 3

    for content in iterate_all(
        pulpcore_bindings.ContentApi.list, repository_version=repo.latest_version_href
    ):
        created_content.add(content.pulp_href.strip("/").split("/")[-2])
        all_content.add(content.pulp_href)

    assert expected_content == created_content

    all_content = all_content.difference(excluded_content)

    return repo, [collection_url, collection_url2], all_content, excluded_content


@pytest.fixture
def repo_with_one_out_collection(
    ansible_bindings, build_and_upload_collection, ansible_repo, monitor_task
):
    """Create a distro serving two collections, one signed, one unsigned."""
    collection, collection_url = build_and_upload_collection()

    # add collection to repo
    body = {"add_content_units": [collection_url]}
    monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(ansible_repo.pulp_href, body).task)

    repo = ansible_bindings.RepositoriesAnsibleApi.read(ansible_repo.pulp_href)

    return repo, collection_url


def test_copy_with_all_content(
    pulpcore_bindings,
    ansible_bindings,
    repo_with_kitted_out_collection,
    ansible_repo_factory,
    monitor_task,
):
    """
    Test copying a collection with all it's associated content
    """
    src_repo, collections, all_content, excluded = repo_with_kitted_out_collection

    dest1 = ansible_repo_factory()
    dest2 = ansible_repo_factory()
    dest3 = ansible_repo_factory()

    dest = (dest1, dest2, dest3)

    task = ansible_bindings.RepositoriesAnsibleApi.copy_collection_version(
        src_repo.pulp_href,
        {
            "collection_versions": collections,
            "destination_repositories": [x.pulp_href for x in dest],
        },
    )

    monitor_task(task.task)

    for repo in dest:
        href = ansible_bindings.RepositoriesAnsibleApi.read(repo.pulp_href).latest_version_href
        dest_content = {
            x.pulp_href
            for x in iterate_all(pulpcore_bindings.ContentApi.list, repository_version=href)
        }

        assert dest_content == all_content

    href = ansible_bindings.RepositoriesAnsibleApi.read(src_repo.pulp_href).latest_version_href
    remaining = {
        c.pulp_href for c in iterate_all(pulpcore_bindings.ContentApi.list, repository_version=href)
    }

    assert remaining == excluded.union(all_content)


def test_move_with_all_content(
    pulpcore_bindings,
    ansible_bindings,
    repo_with_kitted_out_collection,
    ansible_repo_factory,
    monitor_task,
):
    """
    Test moving a collection with all it's associated content
    """
    src_repo, collections, all_content, excluded = repo_with_kitted_out_collection

    dest1 = ansible_repo_factory()
    dest2 = ansible_repo_factory()
    dest3 = ansible_repo_factory()

    dest = (dest1, dest2, dest3)

    task = ansible_bindings.RepositoriesAnsibleApi.move_collection_version(
        src_repo.pulp_href,
        {
            "collection_versions": collections,
            "destination_repositories": [x.pulp_href for x in dest],
        },
    )

    monitor_task(task.task)

    for repo in dest:
        href = ansible_bindings.RepositoriesAnsibleApi.read(repo.pulp_href).latest_version_href
        dest_content = {
            x.pulp_href
            for x in iterate_all(pulpcore_bindings.ContentApi.list, repository_version=href)
        }

        assert dest_content == all_content

    href = ansible_bindings.RepositoriesAnsibleApi.read(src_repo.pulp_href).latest_version_href
    remaining = {
        c.pulp_href for c in iterate_all(pulpcore_bindings.ContentApi.list, repository_version=href)
    }

    assert remaining == excluded


def test_copy_and_sign(
    pulpcore_bindings,
    ansible_bindings,
    ascii_armored_detached_signing_service,
    ansible_repo_factory,
    repo_with_one_out_collection,
    monitor_task,
):
    """Verify that you can copy and sign a collection."""
    src_repo, collection_url = repo_with_one_out_collection

    dest1 = ansible_repo_factory()
    dest2 = ansible_repo_factory()
    dest3 = ansible_repo_factory()

    dest = (dest1, dest2, dest3)

    task = ansible_bindings.RepositoriesAnsibleApi.copy_collection_version(
        src_repo.pulp_href,
        {
            "collection_versions": [collection_url],
            "destination_repositories": [x.pulp_href for x in dest],
            "signing_service": ascii_armored_detached_signing_service.pulp_href,
        },
    )

    monitor_task(task.task)

    for repo in dest:
        href = ansible_bindings.RepositoriesAnsibleApi.read(repo.pulp_href).latest_version_href
        assert pulpcore_bindings.ContentApi.list(repository_version=href).count == 2

        collections = ansible_bindings.ContentCollectionVersionsApi.list(repository_version=href)
        assert collections.count == 1

        signatures = ansible_bindings.ContentCollectionSignaturesApi.list(repository_version=href)
        assert signatures.count == 1

        assert signatures.results[0].signed_collection == collections.results[0].pulp_href


def test_move_and_sign(
    pulpcore_bindings,
    ansible_bindings,
    ascii_armored_detached_signing_service,
    ansible_repo_factory,
    repo_with_one_out_collection,
    monitor_task,
):
    """Verify that you can move and sign a collection."""
    src_repo, collection_url = repo_with_one_out_collection

    dest1 = ansible_repo_factory()
    dest2 = ansible_repo_factory()
    dest3 = ansible_repo_factory()

    dest = (dest1, dest2, dest3)

    task = ansible_bindings.RepositoriesAnsibleApi.move_collection_version(
        src_repo.pulp_href,
        {
            "collection_versions": [collection_url],
            "destination_repositories": [x.pulp_href for x in dest],
            "signing_service": ascii_armored_detached_signing_service.pulp_href,
        },
    )

    monitor_task(task.task)

    for repo in dest:
        href = ansible_bindings.RepositoriesAnsibleApi.read(repo.pulp_href).latest_version_href
        assert pulpcore_bindings.ContentApi.list(repository_version=href).count == 2

        collections = ansible_bindings.ContentCollectionVersionsApi.list(repository_version=href)
        assert collections.count == 1

        signatures = ansible_bindings.ContentCollectionSignaturesApi.list(repository_version=href)
        assert signatures.count == 1

        assert signatures.results[0].signed_collection == collections.results[0].pulp_href

    href = ansible_bindings.RepositoriesAnsibleApi.read(src_repo.pulp_href).latest_version_href
    assert pulpcore_bindings.ContentApi.list(repository_version=href).count == 0
