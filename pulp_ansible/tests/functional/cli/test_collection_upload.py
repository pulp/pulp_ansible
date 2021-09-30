"""Tests that Collections can be uploaded to  Pulp with the ansible-galaxy CLI."""

import random
import string
import subprocess
import tempfile
import os

from pulpcore.client.pulp_ansible import (
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RemotesCollectionApi,
    RepositoriesAnsibleApi,
    RepositoriesAnsibleVersionsApi,
)
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import gen_distribution, gen_repo
from pulp_smash.utils import http_get, uuid4

from pulp_ansible.tests.functional.utils import gen_ansible_client, wait_tasks
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class InstallCollectionTestCase(PulpTestCase):
    """Test whether ansible-galaxy can upload a Collection to Pulp."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        delete_orphans()
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.repo_versions_api = RepositoriesAnsibleVersionsApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.collections_v3api = PulpAnsibleApiV3CollectionsApi(cls.client)
        cls.collections_versions_v3api = PulpAnsibleApiV3CollectionsVersionsApi(cls.client)

    def test_upload_collection(self):
        """Test whether ansible-galaxy can upload a Collection to Pulp."""
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        with tempfile.TemporaryDirectory() as temp_dir:
            collection_name = "".join([random.choice(string.ascii_lowercase) for i in range(26)])
            cmd = "ansible-galaxy collection init --init-path {} pulp.{}".format(
                temp_dir, collection_name
            )
            subprocess.run(cmd.split())

            collection_meta = os.path.join(temp_dir, f"pulp/{collection_name}/meta")
            os.mkdir(collection_meta)
            with open(os.path.join(collection_meta, "runtime.yml"), "w") as runtime:
                runtime.write('requires_ansible: ">=2.9"')

            cmd = "ansible-galaxy collection build --output-path {} {}{}".format(
                temp_dir, temp_dir, "/pulp/" + collection_name + "/"
            )
            subprocess.run(cmd.split())

            repo_version = self.repo_versions_api.read(repo.latest_version_href)
            self.assertEqual(repo_version.number, 0)  # We uploaded 1 collection

            cmd = "ansible-galaxy collection publish -c -s {} {}{}".format(
                distribution.client_url, temp_dir, "/pulp-" + collection_name + "-1.0.0.tar.gz"
            )
            subprocess.run(cmd.split())
            wait_tasks()

        repo = self.repo_api.read(repo.pulp_href)
        repo_version = self.repo_versions_api.read(repo.latest_version_href)
        self.assertEqual(repo_version.number, 1)  # We uploaded 1 collection

    def test_upload_collection_with_requires_ansible(self):
        """Test whether ansible-galaxy can upload a Collection to Pulp."""
        delete_orphans()
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])

        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        collections = self.collections_v3api.list(distribution.base_path)
        self.assertEqual(collections.meta.count, 0)

        temp_path = f"/tmp/{uuid4()}"
        subprocess.run(f"mkdir -p {temp_path}".split())

        content = http_get("https://galaxy.ansible.com/download/pulp-squeezer-0.0.9.tar.gz")
        collection_path = f"{temp_path}/pulp-squeezer-0.0.9.tar.gz"
        with open(collection_path, "wb") as f:
            f.write(content)

        cmd = "ansible-galaxy collection publish -c -s {} {}".format(
            distribution.client_url, collection_path
        )
        subprocess.run(cmd.split())
        wait_tasks()

        collections = self.collections_v3api.list(distribution.base_path)
        self.assertEqual(collections.meta.count, 1)

        repo = self.repo_api.read(repo.pulp_href)
        repo_version = self.repo_versions_api.read(repo.latest_version_href)
        self.assertEqual(repo_version.number, 1)  # We uploaded 1 collection

        version = self.collections_versions_v3api.read(
            "squeezer", "pulp", distribution.base_path, "0.0.9"
        )

        self.assertEqual(version.requires_ansible, ">=2.8")
