"""
Tests PulpExporter and PulpExport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""

import pytest
import uuid

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL
from pulp_ansible.tests.functional.constants import ANSIBLE_FIXTURE_URL


# As long as we cannot run this test in domains, it must not run as parallel.
# Orphan cleanup is unsafe in any scenario here.


@pytest.mark.parametrize("cleanup", [True, False])
def test_export_then_import(
    pulpcore_bindings,
    ansible_bindings,
    gen_object_with_cleanup,
    ansible_repo_factory,
    ansible_role_remote_factory,
    build_and_upload_collection,
    ansible_distribution_factory,
    ascii_armored_detached_signing_service,
    random_image_factory,
    monitor_task,
    monitor_task_group,
    cleanup,
):
    """Issue and evaluate a PulpExport (tests both Create and Read)."""
    # Prepare content
    remote_b = ansible_role_remote_factory(url=ANSIBLE_FIXTURE_URL)
    repo_b = ansible_repo_factory(remote=remote_b.pulp_href)
    sync_b_task = ansible_bindings.RepositoriesAnsibleApi.sync(
        repo_b.pulp_href, AnsibleRepositorySyncURL(remote=remote_b.pulp_href)
    ).task
    repo_a = ansible_repo_factory()
    distro = ansible_distribution_factory(repository=repo_a)
    collection, collection_href = build_and_upload_collection(repo_a)
    signing_body = {
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
        "content_units": ["*"],
    }
    signing_task = ansible_bindings.RepositoriesAnsibleApi.sign(repo_a.pulp_href, signing_body).task

    mark_body = {
        "content_units": ["*"],
        "value": "exportable-mark",
    }
    mark_task = ansible_bindings.RepositoriesAnsibleApi.mark(repo_a.pulp_href, mark_body).task

    deprecation_task = ansible_bindings.ContentCollectionDeprecationsApi.create(
        {
            "namespace": collection.namespace,
            "name": collection.name,
            "repository": repo_a.pulp_href,
        }
    ).task

    namespace_body = {
        "name": collection.namespace,
        "avatar": random_image_factory(),
        "links": [
            {"name": "homepage", "url": "https://example.com"},
            {"name": "github", "url": "https://gh.com"},
        ],
    }
    namespace_task = ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi.create(
        path=distro.base_path, distro_base_path=distro.base_path, **namespace_body
    ).task

    # Collect all the content create tasks
    monitor_task(sync_b_task)
    monitor_task(signing_task)
    monitor_task(mark_task)
    monitor_task(deprecation_task)
    monitor_task(namespace_task)
    # Gather statistics of the original data
    repo_ver_a = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        f"{repo_a.pulp_href}versions/5/"
    )
    repo_ver_b = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        f"{repo_b.pulp_href}versions/1/"
    )

    # Prepare export
    exporter = gen_object_with_cleanup(
        pulpcore_bindings.ExportersPulpApi,
        {
            "name": str(uuid.uuid4()),
            "path": f"/tmp/{uuid.uuid4()}/",
            "repositories": [repo.pulp_href for repo in [repo_a, repo_b]],
        },
    )

    # Export
    task = pulpcore_bindings.ExportersPulpExportsApi.create(exporter.pulp_href, {}).task
    task = monitor_task(task)
    assert len(task.created_resources) == 1
    export = pulpcore_bindings.ExportersPulpExportsApi.read(task.created_resources[0])
    assert export is not None
    assert len(exporter.repositories) == len(export.exported_resources)
    assert export.output_file_info is not None
    for an_export_filename in export.output_file_info.keys():
        assert "//" not in an_export_filename
    export_filename = next(
        f for f in export.output_file_info.keys() if f.endswith("tar.gz") or f.endswith("tar")
    )

    if cleanup:
        # Remove all content from pulp (currently only the genrated content in repo a).
        # Since repo b is synced we cannot safely do this.
        content_a = pulpcore_bindings.ContentApi.list(
            repository_version=f"{repo_a.pulp_href}versions/5/"
        )
        assert content_a.count == 5
        assert content_a.next is None, "Unexpected pagination. Please redesign the test."
        content_a_hrefs = [c.pulp_href for c in content_a.results]
        monitor_task(ansible_bindings.RepositoriesAnsibleApi.delete(repo_a.pulp_href).task)
        cleanup_result = monitor_task(
            pulpcore_bindings.OrphansCleanupApi.cleanup(
                {"orphan_protection_time": 0, "content_hrefs": content_a_hrefs}
            ).task
        )
        assert (
            next(
                (
                    report
                    for report in cleanup_result.progress_reports
                    if report.code == "clean-up.content"
                )
            ).total
            == 5
        )

    # Prepare import
    repo_c = ansible_repo_factory()
    repo_d = ansible_repo_factory()
    repo_mapping = {repo_a.name: repo_c.name, repo_b.name: repo_d.name}
    importer = gen_object_with_cleanup(
        pulpcore_bindings.ImportersPulpApi,
        {"name": str(uuid.uuid4()), "repo_mapping": repo_mapping},
    )

    # Import
    import_response = pulpcore_bindings.ImportersPulpImportsApi.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    repo_c = ansible_bindings.RepositoriesAnsibleApi.read(repo_c.pulp_href)
    repo_d = ansible_bindings.RepositoriesAnsibleApi.read(repo_d.pulp_href)
    assert repo_c.latest_version_href == f"{repo_c.pulp_href}versions/1/"
    assert repo_d.latest_version_href == f"{repo_d.pulp_href}versions/1/"
    repo_ver_c = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        f"{repo_c.pulp_href}versions/1/"
    )
    repo_ver_d = ansible_bindings.RepositoriesAnsibleVersionsApi.read(
        f"{repo_d.pulp_href}versions/1/"
    )
    assert (
        repo_ver_c.content_summary.added["ansible.collection_version"]["count"]
        == repo_ver_a.content_summary.present["ansible.collection_version"]["count"]
    )
    assert (
        repo_ver_c.content_summary.added["ansible.collection_deprecation"]["count"]
        == repo_ver_a.content_summary.present["ansible.collection_deprecation"]["count"]
    )
    assert (
        repo_ver_c.content_summary.added["ansible.collection_signature"]["count"]
        == repo_ver_a.content_summary.present["ansible.collection_signature"]["count"]
    )
    assert (
        repo_ver_c.content_summary.added["ansible.collection_mark"]["count"]
        == repo_ver_a.content_summary.present["ansible.collection_mark"]["count"]
    )
    assert (
        repo_ver_c.content_summary.added["ansible.namespace"]["count"]
        == repo_ver_a.content_summary.present["ansible.namespace"]["count"]
    )
    assert (
        repo_ver_d.content_summary.added["ansible.role"]["count"]
        == repo_ver_b.content_summary.present["ansible.role"]["count"]
    )

    # Import a second time
    import_response = pulpcore_bindings.ImportersPulpImportsApi.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    assert len(pulpcore_bindings.ImportersPulpImportsApi.list(importer.pulp_href).results) == 2
    for repo in [repo_c, repo_d]:
        repo = ansible_bindings.RepositoriesAnsibleApi.read(repo.pulp_href)
        # still only one version as pulp won't create a new version if nothing changed
        assert repo.latest_version_href == f"{repo.pulp_href}versions/1/"
