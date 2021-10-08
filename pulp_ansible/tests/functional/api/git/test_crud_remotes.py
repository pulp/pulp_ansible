# coding=utf-8
"""Tests that CRUD remotes."""
from pulpcore.client.pulp_ansible import RemotesGitApi

from pulp_smash.pulp3.bindings import monitor_task, PulpTestCase

from pulp_ansible.tests.functional.utils import gen_ansible_client, gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CRUDAnsibleGitRemotesTestCase(PulpTestCase):
    """CRUD Ansible Git remotes."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.remote_ansible_git_api = RemotesGitApi(cls.client)

    def test_01_crud_remote(self):
        """Create, Read, Partial Update, and Delete an Ansible Git remote."""
        body = gen_ansible_remote(url="https://github.com/geerlingguy/ansible-role-adminer.git")
        remote = self.remote_ansible_git_api.create(body)
        self.addCleanup(self.remote_ansible_git_api.delete, remote.pulp_href)
        remote = self.remote_ansible_git_api.read(remote.pulp_href)
        for k, v in body.items():
            self.assertEquals(body[k], getattr(remote, k))
        update_body = {"url": "https://github.com/geerlingguy/ansible-role-ansible.git"}
        remote_update = self.remote_ansible_git_api.partial_update(remote.pulp_href, update_body)
        monitor_task(remote_update.task)
        remote = self.remote_ansible_git_api.read(remote.pulp_href)
        self.assertEqual(remote.url, update_body["url"])
        self.assertEqual(remote.metadata_only, False)
        with self.assertRaises(AttributeError):
            getattr(remote, "policy")

    def test_02_metadata_only_remote(self):
        """Create a remote where `metadata_only` is set to True."""
        body = gen_ansible_remote(
            url="https://github.com/geerlingguy/ansible-role-adminer.git", metadata_only=True
        )
        remote = self.remote_ansible_git_api.create(body)
        self.addCleanup(self.remote_ansible_git_api.delete, remote.pulp_href)
        for k, v in body.items():
            self.assertEqual(body[k], getattr(remote, k))
