# coding=utf-8
"""Tests related to upload of collections."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.exceptions import TaskReportError
from pulp_smash.pulp3.constants import ARTIFACTS_PATH
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
        artifact = cls.client.post(ARTIFACTS_PATH, files={"file": collection_content})
        cls.collection = {
            "artifact": artifact["_href"],
            "relative_path": ANSIBLE_COLLECTION_FILE_NAME,
        }

    def test_collection_upload(self):
        """Upload a collection.

        This test targets the following issue:

        * `Pulp #5262 <https://pulp.plan.io/issues/5262>`_
        """
        UPLOAD_PATH = urljoin(self.cfg.get_base_url(), "ansible/collections/")
        response = self.client.using_handler(api.task_handler).post(UPLOAD_PATH, self.collection)

        for key, value in response.items():
            with self.subTest(key=key):
                if key in COLLECTION_METADATA.keys():
                    self.assertEqual(COLLECTION_METADATA[key], value, response)

        with self.assertRaises(TaskReportError) as ctx:
            self.client.using_handler(api.task_handler).post(UPLOAD_PATH, self.collection)

        for key in ("collection_version", "name", "namespace", "version"):
            self.assertIn(
                key, ctx.exception.task["error"]["description"].lower(), ctx.exception.task["error"]
            )

        delete_orphans(self.cfg)
