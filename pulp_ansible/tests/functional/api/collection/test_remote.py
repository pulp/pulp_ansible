"""Tests related to CollectionRemote objects."""
from pulpcore.client.pulp_ansible.exceptions import ApiException

from pulp_ansible.tests.functional.utils import gen_ansible_remote, TestCaseUsingBindings
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CollectionRemoteCase(TestCaseUsingBindings):
    """Test CollectionRemote."""

    def test_remote_with_url_only_is_allowed(self):
        """Assert that a `CollectionRemote` with only a url can be created."""
        body = gen_ansible_remote(url="https://example.com/")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

    def test_token_only_is_allowed(self):
        """Assert that a `CollectionRemote` with `token` and no `auth_url` can be created."""
        body = gen_ansible_remote(url="https://example.com/", token="this is a token string")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

    def test_auth_url_requires_token(self):
        """Assert that a `CollectionRemote` with `auth_url` and no `token` can't be created."""
        body = gen_ansible_remote(url="https://example.com/", auth_url="https://example.com")
        self.assertRaises(ApiException, self.remote_collection_api.create, body)

    def test_remote_urls(self):
        """This tests that the remote url ends with a "/"."""
        body = gen_ansible_remote(url="http://galaxy.ansible.com/api")
        self.assertRaises(ApiException, self.remote_collection_api.create, body)

        body = gen_ansible_remote(url="http://galaxy.example.com")
        self.assertRaises(ApiException, self.remote_collection_api.create, body)

        body = gen_ansible_remote(url="https://galaxy.ansible.com")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)

        body = gen_ansible_remote(url="https://galaxy.ansible.com/")
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)
