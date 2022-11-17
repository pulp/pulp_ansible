"""Tests related to upload of collections."""
import hashlib
from tempfile import NamedTemporaryFile

from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.utils import http_get

from pulpcore.client.pulp_ansible import (
    AnsibleCollectionsApi,
    ContentCollectionVersionsApi,
    ApiException,
)

from pulp_ansible.tests.functional.utils import gen_ansible_client
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


COLLECTION_URL = "https://galaxy.ansible.com/download/pulp-squeezer-0.0.9.tar.gz"


class UploadCollectionTestCase(PulpTestCase):
    """Upload a collection."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        delete_orphans()
        cls.client = gen_ansible_client()
        cls.collections_api = AnsibleCollectionsApi(cls.client)
        cls.content_api = ContentCollectionVersionsApi(cls.client)

    @classmethod
    def tearDownClass(cls):
        """Clean up after tests."""
        delete_orphans()

    def upload_collection(self, url=COLLECTION_URL):
        """Uploada collection."""
        collection_content = http_get(url)
        self.collection_sha256 = hashlib.sha256(collection_content).hexdigest()
        with NamedTemporaryFile() as temp_file:
            temp_file.write(collection_content)
            response = self.collections_api.upload_collection(file=temp_file.name)
            collection_version_href = monitor_task(response.task).created_resources[0]
            return self.content_api.read(collection_version_href)

    def test_collection_upload(self):
        """Upload a collection.

        This test targets the following issue:

        * `Pulp #5262 <https://pulp.plan.io/issues/5262>`_
        """
        response = self.upload_collection()

        self.assertEqual(response.sha256, self.collection_sha256, response)

        with self.assertRaises(ApiException) as exc:
            self.upload_collection()

        assert exc.exception.status == 400
        assert "Artifact already exists" in exc.exception.body

        delete_orphans()
