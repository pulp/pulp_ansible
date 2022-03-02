"""Tests related to Galaxy V3 deprecation."""
from pulp_ansible.tests.functional.utils import (
    gen_ansible_remote,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_smash.pulp3.bindings import monitor_task


class DeprecationTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Test deprecation status sync."""

    def deprecation_scenario(self, **repo_kwargs):
        """Test sync  sync."""
        # Sync down two collections into a repo
        requirements = (
            "collections:\n  - name: testing.k8s_demo_collection\n  - name: pulp.squeezer"
        )

        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file=requirements,
            sync_dependencies=False,
        )
        first_remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, first_remote.pulp_href)

        first_repo = self._create_repo_and_sync_with_remote(first_remote, **repo_kwargs)
        first_distro = self._create_distribution_from_repo(first_repo)

        # Assert the state of deprecated True for testing, False for pulp
        collections = self.collections_v3api.list(first_distro.base_path, namespace="testing")

        self.assertTrue(collections.data[0].deprecated)
        collections = self.collections_v3api.list(first_distro.base_path, namespace="pulp")
        self.assertFalse(collections.data[0].deprecated)

        # Sync a second repo from the first, just the testing namespace
        requirements = "collections:\n  - name: testing.k8s_demo_collection"
        body = gen_ansible_remote(
            url=first_distro.client_url,
            requirements_file=requirements,
            sync_dependencies=False,
            include_pulp_auth=True,
        )
        second_remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, second_remote.pulp_href)

        second_repo = self._create_repo_with_attached_remote_and_sync(second_remote, **repo_kwargs)
        second_distribution = self._create_distribution_from_repo(second_repo)

        # Ensure the second remote received a deprecated=True for the testing namespace collection
        collections = self.collections_v3api.list(
            second_distribution.base_path, namespace="testing"
        )
        self.assertTrue(collections.data[0].deprecated)

        # Change the deprecated status for the testing collection on the original repo to False
        result = self.collections_v3api.update(
            "k8s_demo_collection", "testing", first_distro.base_path, {"deprecated": False}
        )
        monitor_task(result.task)
        collections = self.collections_v3api.list(first_distro.base_path, namespace="testing")
        self.assertFalse(collections.data[0].deprecated)

        # Update the requirements to sync down both collections this time
        requirements = (
            "collections:\n  - name: testing.k8s_demo_collection\n  - name: pulp.squeezer"
        )
        self.remote_collection_api.partial_update(
            second_remote.pulp_href, {"requirements_file": requirements}
        )

        # Sync the second repo again
        self._sync_repo(second_repo)

        # Assert both collections show deprecated=False
        collections = self.collections_v3api.list(second_distribution.base_path)
        for collection in collections.data:
            self.assertFalse(collection.deprecated)

    def test_v3_deprecation(self):
        """Test that the deprecation status is set correctly for collections."""
        self.deprecation_scenario()

    def test_v3_deprecation_with_repo_versions_retained(self):
        """Test that the deprecation status is set correctly for collections."""
        self.deprecation_scenario(retain_repo_versions=1)
