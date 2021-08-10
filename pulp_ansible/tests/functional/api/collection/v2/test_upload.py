"""Tests related to upload of collections."""
import hashlib
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.exceptions import TaskReportError
from pulp_smash.pulp3.bindings import delete_orphans, PulpTestCase
from pulp_smash.utils import http_get

from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class UploadCollectionTestCase(PulpTestCase):
    """Upload a collection."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        delete_orphans()
        cls.client = api.Client(cls.cfg)

        collection_content = http_get(
            "https://galaxy.ansible.com/download/pulp-pulp_installer-3.14.0.tar.gz"
        )
        cls.collection = {"file": ("pulp-pulp_installer-3.14.0.tar.gz", collection_content)}
        cls.collection_sha256 = hashlib.sha256(collection_content).hexdigest()

    def test_collection_upload(self):
        """Upload a collection.

        This test targets the following issue:

        * `Pulp #5262 <https://pulp.plan.io/issues/5262>`_
        """
        UPLOAD_PATH = urljoin(self.cfg.get_base_url(), "ansible/collections/")
        response = self.client.post(UPLOAD_PATH, files=self.collection)

        self.assertEqual(response["sha256"], self.collection_sha256, response)

        with self.assertRaises(TaskReportError) as exc:
            self.client.post(UPLOAD_PATH, files=self.collection)

        self.assertEqual(exc.exception.task["state"], "failed")
        error = exc.exception.task["error"]
        for key in ("artifact", "already", "exists"):
            self.assertIn(key, error["description"].lower(), error)

        delete_orphans()
