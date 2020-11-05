"""Tests related to upload of collections."""
import hashlib
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.exceptions import TaskReportError
from pulp_smash.pulp3.utils import delete_orphans
from pulp_smash.utils import http_get

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_FILE_NAME,
    ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL,
    COLLECTION_METADATA,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class UploadCollectionTestCase(unittest.TestCase):
    """Upload a collection."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg)

        collection_content = http_get(ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL)
        cls.collection = {"file": (ANSIBLE_COLLECTION_FILE_NAME, collection_content)}
        cls.collection_sha256 = hashlib.sha256(collection_content).hexdigest()

    def test_collection_upload(self):
        """Upload a collection.

        This test targets the following issue:

        * `Pulp #5262 <https://pulp.plan.io/issues/5262>`_
        """
        UPLOAD_PATH = urljoin(self.cfg.get_base_url(), "ansible/collections/")
        response = self.client.post(UPLOAD_PATH, files=self.collection)

        for key, value in response.items():
            with self.subTest(key=key):
                if key in COLLECTION_METADATA.keys():
                    self.assertEqual(COLLECTION_METADATA[key], value, response)

        self.assertEqual(response["sha256"], self.collection_sha256, response)

        with self.assertRaises(TaskReportError) as exc:
            self.client.post(UPLOAD_PATH, files=self.collection)

        self.assertEqual(exc.exception.task["state"], "failed")
        error = exc.exception.task["error"]
        for key in ("artifact", "already", "exists"):
            self.assertIn(key, error["description"].lower(), error)

        delete_orphans(self.cfg)
