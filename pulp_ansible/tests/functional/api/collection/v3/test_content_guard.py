import unittest
import requests

from pulpcore.client.pulp_ansible import (
    PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi,
    PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexVersionsApi,
)
from pulp_smash import config

from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    is_galaxy_ng_installed,
)
from pulp_ansible.tests.functional.utils import SyncHelpersMixin, TestCaseUsingBindings
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulpcore import ContentguardsContentRedirectApi, ApiClient as CoreApiClient


class CollectionDownloadTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Test content redirect guard."""

    def setUp(self):
        """Set up the content guard tests."""
        self.requirements_file = "collections:\n  - testing.k8s_demo_collection"
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=self.requirements_file,
            sync_dependencies=False,
        )
        self.remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, self.remote.pulp_href)

        self.first_repo = self._create_repo_and_sync_with_remote(self.remote)
        self.distribution = self._create_distribution_from_repo(self.first_repo)

    def _get_download_url(self, namespace, name):

        collection_api = PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi(self.client)
        versions_api = PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexVersionsApi(
            self.client
        )

        collection = collection_api.read(
            self.distribution.base_path,
            name,
            namespace,
        )

        version = versions_api.read(
            self.distribution.base_path, name, namespace, collection.highest_version["version"]
        )

        return version.download_url

    @unittest.skipIf(
        is_galaxy_ng_installed(),
        (
            "This test fails with galaxy_ng installed because galaxy_ng ensures that "
            "a contentguard is always present on ansible repos."
        ),
    )
    def test_download(self):
        """Test that downloads without content guards work correctly."""
        # Using requests for these tests because the client follows redirects and I need to
        # inspect the URL that gets redirected to
        download_url = self._get_download_url("testing", "k8s_demo_collection")
        cfg = config.get_config()
        response = requests.get(download_url, auth=tuple(cfg.pulp_auth), allow_redirects=False)

        # verify that the download url redirects to the content app
        assert response.is_redirect
        content_app_url = response.headers["Location"]

        # verify that the collection can be downloaded without authentication
        assert "validate_token" not in content_app_url

        collection = requests.get(content_app_url)
        assert collection.status_code == 200

    def test_download_with_content_guard(self):
        """Test that downloads with content guards work correctly."""
        # Using requests for these tests because the client follows redirects and I need to
        # inspect the URL that gets redirected to
        # setup content guard
        cfg = config.get_config()
        configuration = cfg.get_bindings_config()
        core_client = CoreApiClient(configuration)
        guard_client = ContentguardsContentRedirectApi(core_client)
        guard = guard_client.create({"name": "test-content-guard"})

        self.addCleanup(guard_client.delete, guard.pulp_href)

        self.distributions_api.partial_update(
            self.distribution.pulp_href, {"content_guard": guard.pulp_href}
        )

        download_url = self._get_download_url("testing", "k8s_demo_collection")
        response = requests.get(download_url, auth=tuple(cfg.pulp_auth), allow_redirects=False)

        # verify that the download url redirects to the content app
        assert response.is_redirect
        content_app_url = response.headers["Location"]

        # verify that token is present
        assert "validate_token" in content_app_url

        collection = requests.get(content_app_url)
        assert collection.status_code == 200

        # make an unauthenticated call to the content app and verify that it gets
        # rejected
        collection = requests.get(content_app_url.split("?")[0])
        assert collection.status_code == 403
