import pytest
from pulpcore.client.pulp_ansible import (
    # Old APIs
    PulpAnsibleApiV3CollectionsApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    PulpAnsibleApiV3CollectionVersionsAllApi,
    PulpAnsibleApiV3CollectionsAllApi,
    PulpAnsibleApiV3CollectionsVersionsDocsBlobApi,
    # New APIs
    PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsAllVersionsApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsAllCollectionsApi,
    PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsDocsBlobApi,
)


@pytest.fixture(scope="class")
def seeded_distribution(
    ansible_collection_remote_factory,
    ansible_sync_factory,
    ansible_distribution_factory,
    monitor_task,
):
    """Set up the content guard tests."""
    requirements_file = (
        "collections:\n" "  - name: testing.k8s_demo_collection\n" "  - name: pulp.squeezer"
    )
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file=requirements_file,
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)
    distribution = ansible_distribution_factory(repository=repository)
    return distribution


@pytest.fixture(scope="class")
def verify_list(ansible_bindings_client, seeded_distribution):
    def _verify_list(new_api, old_api, query_params, args=[]):
        def is_list_identical(r1, r2):
            d1 = r1.to_dict()
            d2 = r2.to_dict()

            # skip comparing links so that the tests pass when galaxy_ng is installed
            assert d1["meta"] == d2["meta"]
            assert d1["data"] == d2["data"]

        c1 = new_api(ansible_bindings_client)
        c2 = old_api(ansible_bindings_client)

        args_new = [seeded_distribution.base_path, *args]

        # test pagination
        r1 = c1.list(*args_new, limit=1)
        r2 = c2.list(*args, limit=1)

        assert len(r1.data) == 1
        assert len(r2.data) == 1

        is_list_identical(r1, r2)

        # test query params
        r1 = c1.list(*args_new, **query_params)
        r2 = c2.list(*args, **query_params)

        is_list_identical(r1, r2)

        # test no query params
        r1 = c1.list(*args_new)
        r2 = c2.list(*args)

        is_list_identical(r1, r2)

    return _verify_list


@pytest.fixture(scope="class")
def verify_all_collections(ansible_bindings_client, seeded_distribution):
    def _verify_all_collections(new_api, old_api):
        c1 = new_api(ansible_bindings_client)
        c2 = old_api(ansible_bindings_client)
        r1 = c1.list(seeded_distribution.base_path, seeded_distribution.base_path)
        r2 = c2.list(seeded_distribution.base_path)

        assert r1 == r2

    return _verify_all_collections


@pytest.fixture(scope="class")
def verify_read(ansible_bindings_client, seeded_distribution):
    def _verify_read(new_api, old_api, version=None):
        c1 = new_api(ansible_bindings_client)
        c2 = old_api(ansible_bindings_client)

        args = ["k8s_demo_collection", "testing", seeded_distribution.base_path]
        if version:
            args.append(version)

        r1 = c1.read(seeded_distribution.base_path, *args)
        r2 = c2.read(*args)

        assert r1 == r2

    return _verify_read


def test_redirects_are_identical(
    seeded_distribution, verify_list, verify_all_collections, verify_read
):
    """
    Verify new and legacy endpoints are identical.
    """
    verify_list(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
        PulpAnsibleApiV3CollectionsApi,
        {"namespace": "testing"},
        args=[seeded_distribution.base_path],
    )

    verify_list(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
        PulpAnsibleApiV3CollectionsVersionsApi,
        {"is_highest": True},
        args=["k8s_demo_collection", "testing", seeded_distribution.base_path],
    )

    verify_read(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi, PulpAnsibleApiV3CollectionsApi
    )

    verify_read(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
        PulpAnsibleApiV3CollectionsVersionsApi,
        version="0.0.3",
    )

    verify_read(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsDocsBlobApi,
        PulpAnsibleApiV3CollectionsVersionsDocsBlobApi,
        version="0.0.3",
    )

    verify_all_collections(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsAllVersionsApi,
        PulpAnsibleApiV3CollectionVersionsAllApi,
    )

    verify_all_collections(
        PulpAnsibleApiV3PluginAnsibleContentCollectionsAllCollectionsApi,
        PulpAnsibleApiV3CollectionsAllApi,
    )
