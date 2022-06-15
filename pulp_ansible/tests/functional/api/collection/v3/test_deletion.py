import unittest

from pulp_ansible.tests.functional.utils import (
    gen_collection_in_distribution,
    SyncHelpersMixin,
    TestCaseUsingBindings,
)

from pulpcore.client.pulp_ansible.exceptions import ApiException
from pulp_smash.pulp3.bindings import monitor_task


class CollectionDeletionTestCase(TestCaseUsingBindings, SyncHelpersMixin):
    """Test collection deletion."""

    def setUp(self):
        """Set up the collection deletion tests."""
        (self.repo, self.distribution) = self._create_empty_repo_and_distribution()

        self.collection_versions = ["1.0.0", "1.0.1"]

        collection = gen_collection_in_distribution(
            self.distribution.base_path, versions=self.collection_versions
        )

        self.collection_name = collection["name"]
        self.collection_namespace = collection["namespace"]

    def test_collection_deletion(self):
        """Test deleting an entire collection."""
        collections = self.collections_v3api.list(self.distribution.base_path)
        assert collections.meta.count == 1

        resp = self.collections_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )
        monitor_task(resp.task)

        collections = self.collections_v3api.list(self.distribution.base_path)
        assert collections.meta.count == 0

        versions = self.collections_versions_v3api.list(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )

        assert versions.meta.count == 0

        with self.assertRaises(ApiException) as e:
            self.collections_v3api.read(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
            )

            assert e.status == 404

    def test_collection_version_deletion(self):
        """Test deleting a specific collection version."""
        collections = self.collections_v3api.list(self.distribution.base_path)
        assert collections.meta.count == 1

        versions = self.collections_versions_v3api.list(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )
        assert versions.meta.count == len(self.collection_versions)

        # Delete one version
        to_delete = self.collection_versions.pop()

        resp = self.collections_versions_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
            version=to_delete,
        )

        monitor_task(resp.task)

        with self.assertRaises(ApiException) as e:
            self.collections_versions_v3api.read(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
                version=to_delete,
            )
            assert e.status == 404

        # Verify that the collection still exists
        collections = self.collections_v3api.list(self.distribution.base_path)
        assert collections.meta.count == 1

        # Verify that the other versions still exist
        versions = self.collections_versions_v3api.list(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )
        assert versions.meta.count == len(self.collection_versions)

        # Delete the rest of the versions

        for to_delete in self.collection_versions:
            resp = self.collections_versions_v3api.delete(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
                version=to_delete,
            )

            monitor_task(resp.task)

        # Verify all the versions have been deleted
        versions = self.collections_versions_v3api.list(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )

        assert versions.meta.count == 0

        # With all the versions deleted, verify that the collection has also
        # been deleted
        with self.assertRaises(ApiException) as e:
            self.collections_v3api.read(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
            )
            assert e.status == 404

    def test_invalid_deletion(self):
        """Test deleting collections that are dependencies for other collections."""
        dependent_version = self.collection_versions.pop()
        dependent_collection = gen_collection_in_distribution(
            self.distribution.base_path,
            dependencies={f"{self.collection_namespace}.{self.collection_name}": dependent_version},
        )

        err_msg = f"{dependent_collection['namespace']}.{dependent_collection['name']} 1.0.0"

        # Verify entire collection can't be deleted
        with self.assertRaises(ApiException) as e:
            self.collections_v3api.delete(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
            )

            # check error message includes collection that's blocking delete
            assert err_msg in e.body

        # Verify specific version that's used can't be deleted
        with self.assertRaises(ApiException) as e:
            self.collections_versions_v3api.delete(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
                version=dependent_version,
            )
            assert e.status == 400

            # check error message includes collection that's blocking delete
            assert err_msg in e.body

        # Verify non dependent version can be deleted.
        resp = self.collections_versions_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
            version=self.collection_versions[0],
        )

        resp = monitor_task(resp.task)

    def test_delete_deprecated_content(self):
        """Test that deprecated content is removed correctly."""
        # Deprecate the collection
        result = self.collections_v3api.update(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
            body={"deprecated": True},
        )
        monitor_task(result.task)

        resp = self.collections_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )
        monitor_task(resp.task)

        # Verify that all the content is gone
        repo = self.repo_api.read(self.repo.pulp_href)
        latest_version = self.repo_version_api.read(repo.latest_version_href)

        assert len(latest_version.content_summary.present) == 0

    @unittest.skip("needs to use signing fixtures from pulpcore")
    def test_delete_signed_content(self):
        """Test that signature content is removed correctly."""
        create_signing_service = None  # Avoids flake8 complaining since this doesn't exist

        sign_service = create_signing_service()

        # Sign the collections
        body = {
            "content_units": [
                "*",
            ],
            "signing_service": sign_service.pulp_href,
        }
        monitor_task(self.repo_api.sign(self.repo.pulp_href, body).task)

        resp = self.collections_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
        )
        monitor_task(resp.task)

        # Verify that all the content is gone
        repo = self.repo_api.read(self.repo.pulp_href)
        latest_version = self.repo_version_api.read(repo.latest_version_href)

        assert len(latest_version.content_summary.present) == 0

    def test_version_deletion_with_range_of_versions(self):
        """Verify collections can be deleted when another version satisfies requirements."""
        # Create a collection that depends on any version of an existing collection
        gen_collection_in_distribution(
            self.distribution.base_path,
            dependencies={f"{self.collection_namespace}.{self.collection_name}": "*"},
        )

        to_delete = self.collection_versions.pop()

        # Verify the collection version can be deleted as long as there is one version
        # left that satisfies the requirements.
        resp = self.collections_versions_v3api.delete(
            path=self.distribution.base_path,
            name=self.collection_name,
            namespace=self.collection_namespace,
            version=to_delete,
        )

        resp = monitor_task(resp.task)

        # Verify that the last version of the collection can't be deleted

        with self.assertRaises(ApiException) as e:
            self.collections_versions_v3api.delete(
                path=self.distribution.base_path,
                name=self.collection_name,
                namespace=self.collection_namespace,
                version=self.collection_versions[0],
            )

            assert e.status == 400
