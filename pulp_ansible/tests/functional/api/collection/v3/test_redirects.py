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

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
)
from pulp_ansible.tests.functional.utils import SyncHelpersMixin, TestCaseUsingBindings


class CollectionContentGuardDownloadTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Collection content guard download test."""

    def setUp(self):
        """Set up the content guard tests."""
        self.requirements_file = (
            "collections:\n  - name: testing.k8s_demo_collection\n  - name: pulp.squeezer"
        )
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=self.requirements_file,
            sync_dependencies=False,
        )
        self.remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, self.remote.pulp_href)

        self.first_repo = self._create_repo_and_sync_with_remote(self.remote)
        self.distribution = self._create_distribution_from_repo(self.first_repo)

    def _verify_list(self, new_api, old_api, query_params, args=[]):
        def is_list_identical(r1, r2):
            d1 = r1.to_dict()
            d2 = r2.to_dict()

            # skip comparing links so that the tests pass when galaxy_ng is installed
            assert d1["meta"] == d2["meta"]
            assert d1["data"] == d2["data"]

        c1 = new_api(self.client)
        c2 = old_api(self.client)

        args_new = [self.distribution.base_path, *args]

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

    def _verify_all_collections(self, new_api, old_api):
        c1 = new_api(self.client)
        c2 = old_api(self.client)
        r1 = c1.list(self.distribution.base_path, self.distribution.base_path)
        r2 = c2.list(self.distribution.base_path)

        assert r1 == r2

    def _verify_read(self, new_api, old_api, version=None):
        c1 = new_api(self.client)
        c2 = old_api(self.client)

        args = ["k8s_demo_collection", "testing", self.distribution.base_path]
        if version:
            args.append(version)

        r1 = c1.read(self.distribution.base_path, *args)
        r2 = c2.read(*args)

        assert r1 == r2

    def test_redirects_are_identical(self):
        """
        Verify new and legacy endpoints are identical.
        """
        self._verify_list(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi,
            PulpAnsibleApiV3CollectionsApi,
            {"namespace": "testing"},
            args=[self.distribution.base_path],
        )

        self._verify_list(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
            PulpAnsibleApiV3CollectionsVersionsApi,
            {"is_highest": True},
            args=["k8s_demo_collection", "testing", self.distribution.base_path],
        )

        self._verify_read(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexApi, PulpAnsibleApiV3CollectionsApi
        )

        self._verify_read(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
            PulpAnsibleApiV3CollectionsVersionsApi,
            version="0.0.3",
        )

        self._verify_read(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsIndexVersionsDocsBlobApi,
            PulpAnsibleApiV3CollectionsVersionsDocsBlobApi,
            version="0.0.3",
        )

        self._verify_all_collections(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsAllVersionsApi,
            PulpAnsibleApiV3CollectionVersionsAllApi,
        )

        self._verify_all_collections(
            PulpAnsibleApiV3PluginAnsibleContentCollectionsAllCollectionsApi,
            PulpAnsibleApiV3CollectionsAllApi,
        )
