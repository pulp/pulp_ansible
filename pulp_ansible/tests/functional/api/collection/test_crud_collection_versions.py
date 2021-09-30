"""Tests related to sync ansible plugin collection content type."""
from tempfile import NamedTemporaryFile
from pulp_smash import api, config
from pulp_smash.pulp3.bindings import PulpTestCase, delete_orphans, monitor_task
from pulp_smash.pulp3.utils import gen_repo, sync
from pulp_smash.utils import http_get

from pulpcore.client.pulp_ansible import ContentCollectionVersionsApi
from pulpcore.client.pulp_ansible.exceptions import ApiException


from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_COLLECTION_VERSION_CONTENT_PATH,
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    ANSIBLE_REPO_PATH,
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote, skip_if
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ListContentVersionsCase(PulpTestCase):
    """Test listing CollectionVersions."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)

    def test_tags_filter(self):
        """Filter CollectionVersions by using the tags filter.

        This test targets the following issue:

        * `Pulp #5571 <https://pulp.plan.io/issues/5571>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the remote.
        3. Attempt to filter the CollectionVersions by different tags

        Note that the testing.k8s_demo_collection collection has tags 'k8s' and 'kubernetes'.
        """
        repo = self.client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        # Sync the repository.
        sync(self.cfg, remote, repo)

        # filter collection versions by tags
        params = {"tags": "nada"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 0, collections)

        params = {"tags": "k8s"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 1, collections)

        params = {"tags": "k8s,kubernetes"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 1, collections)

        params = {"tags": "nada,k8s"}
        collections = self.client.get(ANSIBLE_COLLECTION_VERSION_CONTENT_PATH, params=params)
        self.assertEqual(len(collections), 0, collections)


class ContentUnitTestCase(PulpTestCase):
    """CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp #3445 <https://pulp.plan.io/issues/3445>`_
    * `Pulp Smash #870 <https://github.com/pulp/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        delete_orphans()
        cls.content_unit = {}
        cls.cv_content_api = ContentCollectionVersionsApi(gen_ansible_client())

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans()

    def upload_collection(self, namespace="pulp", name="squeezer", version="0.0.9"):
        """Upload collection."""
        url = f"https://galaxy.ansible.com/download/{namespace}-{name}-{version}.tar.gz"
        collection_content = http_get(url)
        with NamedTemporaryFile() as temp_file:
            temp_file.write(collection_content)
            return self.cv_content_api.create(
                file=temp_file.name, namespace=namespace, name=name, version=version
            )

    def test_01_create_content_unit(self):
        """Create content unit."""
        attrs = dict(namespace="pulp", name="squeezer", version="0.0.9")
        response = self.upload_collection(**attrs)
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.cv_content_api.read(created_resources[0])
        self.content_unit.update(content_unit.to_dict())
        for key, val in attrs.items():
            with self.subTest(key=key):
                self.assertEqual(self.content_unit[key], val)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_unit(self):
        """Read a content unit by its href."""
        content_unit = self.cv_content_api.read(self.content_unit["pulp_href"]).to_dict()
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_units(self):
        """Read a content unit by its pkg_id."""
        page = self.cv_content_api.list(
            namespace=self.content_unit["namespace"], name=self.content_unit["name"]
        )
        self.assertEqual(len(page.results), 1)
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(page.results[0].to_dict()[key], val)

    @skip_if(bool, "content_unit", False)
    def test_03_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = {"name": "testing"}
        with self.assertRaises(AttributeError) as exc:
            self.cv_content_api.partial_update(self.content_unit["pulp_href"], attrs)
        msg = "object has no attribute 'partial_update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_03_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = {"name": "testing"}
        with self.assertRaises(AttributeError) as exc:
            self.cv_content_api.update(self.content_unit["pulp_href"], attrs)
        msg = "object has no attribute 'update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_04_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(AttributeError) as exc:
            self.cv_content_api.delete(self.content_unit["pulp_href"])
        msg = "object has no attribute 'delete'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_05_duplicate_raise_error(self):
        """Attempt to create duplicate collection."""
        attrs = dict(namespace="pulp", name="squeezer", version="0.0.9")
        with self.assertRaises(ApiException) as ctx:
            self.upload_collection(**attrs)
        self.assertIn(
            "The fields namespace, name, version must make a unique set.", ctx.exception.body
        )
