"""
Tests PulpImporter and PulpImport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS and ALLOWED_IMPORT_PATHS settings contain "/tmp" - all tests
will fail if this is not the case.
"""

from pulp_smash import cli
from pulp_smash.utils import uuid4
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, monitor_task_group

from pulp_ansible.tests.functional.api.test_export import BaseExport
from pulp_ansible.tests.functional.constants import TRUNCATE_TABLES_QUERY_BASH
from pulp_ansible.tests.functional.utils import get_psql_smash_cmd

from pulpcore.client.pulpcore import (
    ImportersPulpApi,
    ImportersPulpImportsApi,
)
from pulpcore.client.pulp_ansible import PulpAnsibleTagsApi


class BaseImport(BaseExport):
    """
    Base functionality for PulpImporter and PulpImport test classes.
    """

    @classmethod
    def _create_export(cls, chunked={}):
        export_response = cls.exports_api.create(cls.exporter.pulp_href, chunked)
        monitor_task(export_response.task)
        task = cls.api_client.get(export_response.task)
        resources = task["created_resources"]
        export_href = resources[0]
        export = cls.exports_api.read(export_href)
        return export

    @classmethod
    def setUpClass(cls):
        """Performs export 1 time."""
        super().setUpClass()
        cls.import_repos = []
        cls.importer_api = ImportersPulpApi(cls.core_client)
        cls.imports_api = ImportersPulpImportsApi(cls.core_client)
        cls.tags_api = PulpAnsibleTagsApi(cls.client)
        cls.exporter, _ = cls._create_exporter(cls, False)
        cls.export = cls._create_export()

    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        for repo in cls.import_repos:
            cls.repo_api.delete(repo.pulp_href)
        delete_orphans()

        cli_client = cli.Client(cls.cfg)
        cmd = ("rm", "-rf", cls.exporter.path)
        cli_client.run(cmd, sudo=True)

    def _clean_database(self):
        cli_client = cli.Client(self.cfg)
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        cli_client.run(cmd, sudo=True)

    def _setup_import(self):
        """Set database to a clean state."""
        self.import_repos = []
        self._clean_database()
        self._setup_repositories(self.import_repos)

    def _create_importer(self, name=None, cleanup=True):
        """Create an importer."""
        mapping = {}
        if not name:
            name = uuid4()

        for idx, repo in enumerate(self.export_repos):
            mapping[repo.name] = self.import_repos[idx].name

        body = {
            "name": name,
            "repo_mapping": mapping,
        }

        importer = self.importer_api.create(body)

        if cleanup:
            self.addCleanup(self.importer_api.delete, importer.pulp_href)

        return importer

    def _perform_import(self, importer, chunked=False):
        """Perform an import with importer."""
        if chunked:
            filenames = [
                f for f in list(self.chunked_export.output_file_info.keys()) if f.endswith("json")
            ]
            import_response = self.imports_api.create(importer.pulp_href, {"toc": filenames[0]})
        else:
            filenames = [
                f for f in list(self.export.output_file_info.keys()) if f.endswith("tar.gz")
            ]
            import_response = self.imports_api.create(importer.pulp_href, {"path": filenames[0]})

        task_group = monitor_task_group(import_response.task_group)
        return task_group


class PulpImportTestCase(BaseImport):
    """
    Basic tests for PulpImporter and PulpImport.
    """

    def test_import(self):
        """Test an import."""
        self._setup_import()
        importer = self._create_importer()
        task_group = self._perform_import(importer)
        self.assertEqual(len(self.import_repos) + 1, task_group.completed)
        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)
            repo_ver = self.repo_ver_api.read(repo.latest_version_href)
            added = repo_ver.content_summary.added
            if "ansible.role" in added.keys():
                self.assertEqual(self.export_content_count["role"], added["ansible.role"]["count"])
            elif "ansible.collection_version" in added.keys():
                self.assertEqual(
                    self.export_content_count["collection_version"],
                    added["ansible.collection_version"]["count"],
                )
            elif "ansible.collection_deprecation" in added.keys():
                self.assertEqual(
                    self.export_content_count["collection_deprecation"],
                    added["ansible.collection_deprecation"]["count"],
                )
        tags = self.tags_api.list()
        self.assertEqual(tags.count, 2)

    def test_import_double(self):
        """Test two imports of our export."""
        self._setup_import()
        importer = self._create_importer()
        self._perform_import(importer)
        self._perform_import(importer)

        imports = self.imports_api.list(importer.pulp_href).results
        self.assertEqual(len(imports), 2)

        for repo in self.import_repos:
            repo = self.repo_api.read(repo.pulp_href)
            # still only one version as pulp won't create a new version if nothing changed
            self.assertEqual(f"{repo.pulp_href}versions/1/", repo.latest_version_href)
