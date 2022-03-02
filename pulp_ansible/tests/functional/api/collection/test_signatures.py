"""Tests functionality around Collection-Version Signatures."""
import tarfile
from tempfile import TemporaryDirectory
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTaskError
from pulp_ansible.tests.functional.utils import (
    create_signing_service,
    delete_signing_service,
    gen_repo,
    gen_ansible_remote,
    gen_distribution,
    get_content,
    run_signing_script,
    SyncHelpersMixin,
    TestCaseUsingBindings,
    skip_if,
)
from pulp_ansible.tests.functional.constants import TEST_COLLECTION_CONFIGS
from orionutils.generator import build_collection
from pulpcore.client.pulp_ansible import AnsibleCollectionsApi, ContentCollectionSignaturesApi
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CRUDCollectionVersionSignatures(TestCaseUsingBindings, SyncHelpersMixin):
    """
    CRUD CollectionVersionSignatures.

    This test targets the following issues:

    * `Pulp #757 <https://github.com/pulp/pulp_ansible/issues/757>`_
    * `Pulp #758 <https://github.com/pulp/pulp_ansible/issues/758>`_
    """

    @classmethod
    def setUpClass(cls):
        """Sets up signing service used for creating signatures."""
        super().setUpClass()
        delete_orphans()
        cls.sign_service = create_signing_service()
        cls.collections = []
        cls.signed_collections = []
        cls.repo = {}
        cls.sig_api = ContentCollectionSignaturesApi(cls.client)
        col_api = AnsibleCollectionsApi(cls.client)
        for i in range(5):
            collection = build_collection("skeleton", config=TEST_COLLECTION_CONFIGS[i])
            response = col_api.upload_collection(collection.filename)
            task = monitor_task(response.task)
            cls.collections.append(task.created_resources[0])
        # Locally sign the last collection
        cls.t = TemporaryDirectory()
        with tarfile.open(collection.filename, mode="r") as tar:
            filename = f"{cls.t.name}/MANIFEST.json"
            tar.extract("MANIFEST.json", path=cls.t.name)
        cls.last_signed_filenames = run_signing_script(filename)

    @classmethod
    def tearDownClass(cls):
        """Deletes repository and removes any content and signatures."""
        cls.t.cleanup()
        monitor_task(cls.repo_api.delete(cls.repo["pulp_href"]).task)
        delete_signing_service(cls.sign_service.name)
        delete_orphans()

    def test_00_create_signed_collections(self):
        """Test collection signatures can be created through the sign task."""
        repo = self.repo_api.create(gen_repo())
        first_four = self.collections[:4]
        body = {"add_content_units": first_four}
        monitor_task(self.repo_api.modify(repo.pulp_href, body).task)

        body = {"content_units": first_four, "signing_service": self.sign_service.pulp_href}
        monitor_task(self.repo_api.sign(repo.pulp_href, body).task)
        repo = self.repo_api.read(repo.pulp_href)
        self.repo.update(repo.to_dict())

        self.assertEqual(int(repo.latest_version_href[-2]), 2)
        content_response = get_content(self.repo)
        self.assertIn("ansible.collection_signature", content_response)
        self.assertEqual(len(content_response["ansible.collection_signature"]), 4)
        self.signed_collections.extend(content_response["ansible.collection_signature"])

    @skip_if(bool, "signed_collections", False)
    def test_01_upload_signed_collections(self):
        """Test that collection signatures can be uploaded."""
        last_col = self.collections[-1]
        signature = self.last_signed_filenames["signature"]
        # Check that invalid signatures can't be uploaded
        with self.assertRaises(PulpTaskError):
            task = self.sig_api.create(signed_collection=self.collections[0], file=signature)
            monitor_task(task.task)
        # Proper upload
        task = self.sig_api.create(signed_collection=last_col, file=signature)
        sig = monitor_task(task.task).created_resources[0]
        self.assertIn("content/ansible/collection_signatures/", sig)

    @skip_if(bool, "signed_collections", False)
    def test_02_read_signed_collection(self):
        """Test that a collection's signature can be read."""
        signature = self.sig_api.read(self.signed_collections[0]["pulp_href"])
        self.assertIn(signature.signed_collection, self.collections)
        self.assertEqual(signature.signing_service, self.sign_service.pulp_href)

    @skip_if(bool, "signed_collections", False)
    def test_03_read_signed_collections(self):
        """Test that collection signatures can be listed."""
        signatures = self.sig_api.list(repository_version=self.repo["latest_version_href"])
        self.assertEqual(signatures.count, len(self.signed_collections))
        signature_set = set([s.pulp_href for s in signatures.results])
        self.assertEqual(signature_set, {s["pulp_href"] for s in self.signed_collections})

    @skip_if(bool, "signed_collections", False)
    def test_04_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = {"pubkey_fingerprint": "testing"}
        with self.assertRaises(AttributeError) as exc:
            self.sig_api.partial_update(self.signed_collections[0], attrs)
        msg = "object has no attribute 'partial_update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "signed_collections", False)
    def test_05_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = {"pubkey_fingerprint": "testing"}
        with self.assertRaises(AttributeError) as exc:
            self.sig_api.update(self.signed_collections[0]["pulp_href"], attrs)
        msg = "object has no attribute 'update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "signed_collections", False)
    def test_06_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(AttributeError) as exc:
            self.sig_api.delete(self.signed_collections[0]["pulp_href"])
        msg = "object has no attribute 'delete'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "signed_collections", False)
    def test_07_duplicate(self):
        """Attempt to create a signature duplicate through signing task and upload."""
        first_four = self.collections[:4]
        body = {"content_units": first_four, "signing_service": self.sign_service.pulp_href}
        result = monitor_task(self.repo_api.sign(self.repo["pulp_href"], body).task)
        repo = self.repo_api.read(self.repo["pulp_href"])

        self.assertEqual(repo.latest_version_href, self.repo["latest_version_href"])
        self.assertEqual(len(result.created_resources), 0)

        with self.assertRaises(PulpTaskError):
            signature = self.last_signed_filenames["signature"]
            task = self.sig_api.create(signed_collection=self.collections[-1], file=signature)
            monitor_task(task.task)


class CollectionSignatureSyncing(TestCaseUsingBindings, SyncHelpersMixin):
    """
    Tests for syncing Collections Signatures.

    This test targets the following issues:

    * `Pulp #748 <https://github.com/pulp/pulp_ansible/issues/748>`_
    """

    @classmethod
    def setUpClass(cls):
        """Set up two distros for the sync tests."""
        super().setUpClass()
        collections = []
        cls.signing_service = create_signing_service()
        col_api = AnsibleCollectionsApi(cls.client)
        for i in range(4):
            collection = build_collection("skeleton", config=TEST_COLLECTION_CONFIGS[i])
            response = col_api.upload_collection(collection.filename)
            task = monitor_task(response.task)
            collections.append(task.created_resources[0])

        cls.repo = cls.repo_api.create(gen_repo())
        body = {"add_content_units": collections}
        monitor_task(cls.repo_api.modify(cls.repo.pulp_href, body).task)

        body = {"content_units": collections[:2], "signing_service": cls.signing_service.pulp_href}
        monitor_task(cls.repo_api.sign(cls.repo.pulp_href, body).task)
        body = {"content_units": collections[2:], "signing_service": cls.signing_service.pulp_href}
        monitor_task(cls.repo_api.sign(cls.repo.pulp_href, body).task)

        body = gen_distribution(repository=cls.repo.pulp_href)
        distro_href = monitor_task(cls.distributions_api.create(body).task).created_resources[0]
        cls.distro1 = cls.distributions_api.read(distro_href)
        body = gen_distribution(repository_version=f"{cls.repo.versions_href}2/")
        distro_href = monitor_task(cls.distributions_api.create(body).task).created_resources[0]
        cls.distro2 = cls.distributions_api.read(distro_href)

    @classmethod
    def tearDownClass(cls):
        """Destroys the distros and repos used for the tests."""
        monitor_task(cls.repo_api.delete(cls.repo.pulp_href).task)
        monitor_task(cls.distributions_api.delete(cls.distro1.pulp_href).task)
        monitor_task(cls.distributions_api.delete(cls.distro2.pulp_href).task)
        delete_signing_service(cls.signing_service.name)
        delete_orphans()

    def test_sync_signatures(self):
        """Test that signatures are also synced."""
        body = gen_ansible_remote(self.distro1.client_url, include_pulp_auth=True)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)
        repo = self._create_repo_and_sync_with_remote(remote)

        content_response = get_content(repo.to_dict())
        self.assertEqual(len(content_response["ansible.collection_version"]), 4)
        self.assertEqual(len(content_response["ansible.collection_signature"]), 4)

    def test_sync_signatures_only(self):
        """Test that only collections with a signatures are synced when specified."""
        body = gen_ansible_remote(self.distro2.client_url, signed_only=True, include_pulp_auth=True)
        remote = self.remote_collection_api.create(body)
        self.addCleanup(self.remote_collection_api.delete, remote.pulp_href)
        repo = self._create_repo_and_sync_with_remote(remote)

        content_response = get_content(repo.to_dict())
        self.assertEqual(len(content_response["ansible.collection_version"]), 2)
        self.assertEqual(len(content_response["ansible.collection_signature"]), 2)
