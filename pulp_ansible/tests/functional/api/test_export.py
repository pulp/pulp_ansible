"""
Tests PulpExporter and PulpExport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""
from pulp_smash import api, cli, config
from pulp_smash.utils import uuid4
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task


from pulp_smash.pulp3.utils import gen_repo

from pulp_ansible.tests.functional.utils import gen_ansible_remote, TestCaseUsingBindings

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL, RepositoriesAnsibleVersionsApi
from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ExportersPulpApi,
    ExportersPulpExportsApi,
)


class BaseExport(TestCaseUsingBindings):
    """
    Base functionality for Exporter and Export test classes.

    The export process isn't possible without repositories having been sync'd - arranging for
    that to happen once per-class (instead of once-per-test) is the primary purpose of this parent
    class.
    """

    @classmethod
    def _setup_repositories(cls, repos):
        """
        Sets up and saves two repositories.
        """
        repo_a = cls.repo_api.create(gen_repo())
        repo_b = cls.repo_api.create(gen_repo())
        repos.extend([repo_a, repo_b])

    @classmethod
    def _setup_remotes(cls):
        """
        Sets up and saves a role remote and collection remote.
        """
        body = gen_ansible_remote(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - testing.k8s_demo_collection",
        )
        remote_a = cls.remote_collection_api.create(body)
        remote_b = cls.remote_role_api.create(gen_ansible_remote())
        cls.remotes.extend([remote_a, remote_b])

    @classmethod
    def _setup_content(cls):
        cls._setup_repositories(cls.export_repos)
        cls._setup_remotes()
        repository_sync_data_a = AnsibleRepositorySyncURL(remote=cls.remotes[0].pulp_href)
        repository_sync_data_b = AnsibleRepositorySyncURL(remote=cls.remotes[1].pulp_href)
        sync_response_a = cls.repo_api.sync(cls.export_repos[0].pulp_href, repository_sync_data_a)
        sync_response_b = cls.repo_api.sync(cls.export_repos[1].pulp_href, repository_sync_data_b)
        monitor_task(sync_response_a.task)
        monitor_task(sync_response_b.task)
        repo_ver_a = cls.repo_ver_api.read(f"{cls.export_repos[0].pulp_href}versions/1/")
        repo_ver_b = cls.repo_ver_api.read(f"{cls.export_repos[1].pulp_href}versions/1/")
        cls.export_content_count["collection_version"] = repo_ver_a.content_summary.added[
            "ansible.collection_version"
        ]["count"]
        cls.export_content_count["collection_deprecation"] = repo_ver_a.content_summary.added[
            "ansible.collection_deprecation"
        ]["count"]
        cls.export_content_count["role"] = repo_ver_b.content_summary.added["ansible.role"]["count"]

    @classmethod
    def setUpClass(cls):
        """Sets up apis."""
        super().setUpClass()
        cls.export_repos = []
        cls.export_content_count = {}
        cls.remotes = []
        cls.cfg = config.get_config()
        cls.api_client = api.Client(cls.cfg, api.json_handler)
        cls.core_client = CoreApiClient(configuration=cls.cfg.get_bindings_config())
        cls.exporter_api = ExportersPulpApi(cls.core_client)
        cls.exports_api = ExportersPulpExportsApi(cls.core_client)
        cls.repo_ver_api = RepositoriesAnsibleVersionsApi(cls.client)
        cls._setup_content()

    @classmethod
    def tearDownClass(cls):
        """Clean up after ourselves."""
        for repo in cls.export_repos:
            cls.repo_api.delete(repo.pulp_href)
        cls.remote_collection_api.delete(cls.remotes[0].pulp_href)
        cls.remote_role_api.delete(cls.remotes[1].pulp_href)
        delete_orphans()

    def _delete_exporter(self, exporter):
        """
        Utility routine to delete an exporter.

        Delete even with existing last_export should now Just Work
        (as of https://pulp.plan.io/issues/6555)
        """
        cli_client = cli.Client(self.cfg)
        cmd = ("rm", "-rf", exporter.path)
        cli_client.run(cmd, sudo=True)

        self.exporter_api.delete(exporter.pulp_href)

    def _create_exporter(self, cleanup=True):
        """
        Utility routine to create an exporter for the available repositories.
        """
        body = {
            "name": uuid4(),
            "path": "/tmp/{}/".format(uuid4()),
            "repositories": [repo.pulp_href for repo in self.export_repos],
        }
        exporter = self.exporter_api.create(body)
        if cleanup:
            self.addCleanup(self._delete_exporter, exporter)
        return exporter, body


class PulpExportAnsibleTestCase(BaseExport):
    """Test PulpExport CRDL methods (Update is not allowed)."""

    def _gen_export(self, exporter, body={}):
        """Create and read back an export for the specified PulpExporter."""
        export_response = self.exports_api.create(exporter.pulp_href, body)
        monitor_task(export_response.task)
        task = self.api_client.get(export_response.task)
        resources = task["created_resources"]
        self.assertEqual(1, len(resources))
        export_href = resources[0]
        export = self.exports_api.read(export_href)
        self.assertIsNotNone(export)
        return export

    def test_export(self):
        """Issue and evaluate a PulpExport (tests both Create and Read)."""
        (exporter, body) = self._create_exporter(cleanup=False)
        try:
            export = self._gen_export(exporter)
            self.assertEqual(len(exporter.repositories), len(export.exported_resources))
            self.assertIsNotNone(export.output_file_info)
            for an_export_filename in export.output_file_info.keys():
                self.assertFalse("//" in an_export_filename)

        finally:
            self._delete_exporter(exporter)
