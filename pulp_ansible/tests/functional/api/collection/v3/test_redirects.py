import pytest


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
def verify_list(ansible_bindings, seeded_distribution):
    def _verify_list(new_api, old_api, query_params, args=[]):
        def is_list_identical(r1, r2):
            d1 = r1.to_dict()
            d2 = r2.to_dict()

            # skip comparing links so that the tests pass when galaxy_ng is installed
            assert d1["meta"] == d2["meta"]
            assert d1["data"] == d2["data"]

        args_new = [seeded_distribution.base_path, *args]

        # test pagination
        r1 = new_api.list(*args_new, limit=1)
        r2 = old_api.list(*args, limit=1)

        assert len(r1.data) == 1
        assert len(r2.data) == 1

        is_list_identical(r1, r2)

        # test query params
        r1 = new_api.list(*args_new, **query_params)
        r2 = old_api.list(*args, **query_params)

        is_list_identical(r1, r2)

        # test no query params
        r1 = new_api.list(*args_new)
        r2 = old_api.list(*args)

        is_list_identical(r1, r2)

    return _verify_list


@pytest.fixture(scope="class")
def verify_all_collections(seeded_distribution):
    def _verify_all_collections(new_api, old_api):
        r1 = new_api.list(seeded_distribution.base_path, seeded_distribution.base_path)
        r2 = old_api.list(seeded_distribution.base_path)

        assert r1 == r2

    return _verify_all_collections


@pytest.fixture(scope="class")
def verify_read(ansible_bindings, seeded_distribution):
    def _verify_read(new_api, old_api, version=None):
        args = ["k8s_demo_collection", "testing", seeded_distribution.base_path]
        if version:
            args.append(version)

        r1 = new_api.read(seeded_distribution.base_path, *args)
        r2 = old_api.read(*args)

        assert r1 == r2

    return _verify_read


class TestRedirectsAreIdentical:
    """
    Verify new and legacy endpoints are identical.
    """

    def test_redirect_collections_list(self, ansible_bindings, seeded_distribution, verify_list):
        verify_list(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
            ansible_bindings.PulpAnsibleApiV3CollectionsApi,
            {"namespace": "testing"},
            args=[seeded_distribution.base_path],
        )

    def test_redirect_collections_versions_list(
        self, ansible_bindings, seeded_distribution, verify_list
    ):

        verify_list(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
            ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi,
            {},
            args=["k8s_demo_collection", "testing", seeded_distribution.base_path],
        )

    def test_redirect_collections_read(self, ansible_bindings, seeded_distribution, verify_read):
        verify_read(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
            ansible_bindings.PulpAnsibleApiV3CollectionsApi,
        )

    def test_redirect_collections_versions_read(
        self, ansible_bindings, seeded_distribution, verify_read
    ):
        verify_read(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
            ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi,
            version="0.0.3",
        )

    def test_redirect_collections_versions_docs_blob_read(
        self, ansible_bindings, seeded_distribution, verify_read
    ):
        verify_read(
            getattr(
                ansible_bindings,
                "PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsDocsBlobApi",
            ),
            ansible_bindings.PulpAnsibleApiV3CollectionsVersionsDocsBlobApi,
            version="0.0.3",
        )

    @pytest.mark.skip("https://github.com/OpenAPITools/openapi-generator/issues/20661")
    def test_redirect_collection_versions_all(
        self, ansible_bindings, seeded_distribution, verify_all_collections
    ):
        verify_all_collections(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsAllVersionsApi,
            ansible_bindings.PulpAnsibleApiV3CollectionVersionsAllApi,
        )

    def test_redirect_collections_all(
        self, ansible_bindings, seeded_distribution, verify_all_collections
    ):
        verify_all_collections(
            ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentCollectionsAllCollectionsApi,
            ansible_bindings.PulpAnsibleApiV3CollectionsAllApi,
        )
