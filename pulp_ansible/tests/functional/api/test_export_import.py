"""
Tests PulpExporter and PulpExport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""

import pytest
import uuid

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL
from pulp_ansible.tests.functional.constants import ANSIBLE_FIXTURE_URL


@pytest.mark.parallel
def test_export_then_import(
    gen_object_with_cleanup,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    ansible_role_remote_factory,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    ansible_distribution_factory,
    galaxy_v3_plugin_namespaces_api_client,
    exporters_pulp_api_client,
    exporters_pulp_exports_api_client,
    importers_pulp_api_client,
    importers_pulp_imports_api_client,
    ascii_armored_detached_signing_service,
    random_image_factory,
    monitor_task,
    monitor_task_group,
):
    """Issue and evaluate a PulpExport (tests both Create and Read)."""
    # Prepare content
    remote_a = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
    )
    remote_b = ansible_role_remote_factory(url=ANSIBLE_FIXTURE_URL)
    repo_a = ansible_repo_factory()
    repo_b = ansible_repo_factory()
    sync_response_a = ansible_repo_api_client.sync(
        repo_a.pulp_href, AnsibleRepositorySyncURL(remote=remote_a.pulp_href)
    )
    sync_response_b = ansible_repo_api_client.sync(
        repo_b.pulp_href, AnsibleRepositorySyncURL(remote=remote_b.pulp_href)
    )
    monitor_task(sync_response_a.task)
    monitor_task(sync_response_b.task)
    signing_body = {
        "signing_service": ascii_armored_detached_signing_service.pulp_href,
        "content_units": ["*"],
    }
    monitor_task(ansible_repo_api_client.sign(repo_a.pulp_href, signing_body).task)
    repo_ver_a = ansible_repo_version_api_client.read(f"{repo_a.pulp_href}versions/2/")
    repo_ver_b = ansible_repo_version_api_client.read(f"{repo_b.pulp_href}versions/1/")

    mark_body = {
        "content_units": ["*"],
        "value": "exportable-mark",
    }
    monitor_task(ansible_repo_api_client.mark(repo_a.pulp_href, mark_body).task)
    repo_ver_a = ansible_repo_version_api_client.read(f"{repo_a.pulp_href}versions/3/")

    distro = ansible_distribution_factory(repository=repo_a)
    namespace_body = {
        "name": "example",
        "avatar": random_image_factory(),
        "links": [
            {"name": "homepage", "url": "https://example.com"},
            {"name": "github", "url": "https://gh.com"},
        ],
    }
    task = galaxy_v3_plugin_namespaces_api_client.create(
        path=distro.base_path, distro_base_path=distro.base_path, **namespace_body
    )
    monitor_task(task.task)
    repo_ver_a = ansible_repo_version_api_client.read(f"{repo_a.pulp_href}versions/4/")

    # Prepare export
    exporter = gen_object_with_cleanup(
        exporters_pulp_api_client,
        {
            "name": str(uuid.uuid4()),
            "path": f"/tmp/{uuid.uuid4()}/",
            "repositories": [repo.pulp_href for repo in [repo_a, repo_b]],
        },
    )

    # Export
    task = exporters_pulp_exports_api_client.create(exporter.pulp_href, {}).task
    task = monitor_task(task)
    assert len(task.created_resources) == 1
    export = exporters_pulp_exports_api_client.read(task.created_resources[0])
    assert export is not None
    assert len(exporter.repositories) == len(export.exported_resources)
    assert export.output_file_info is not None
    for an_export_filename in export.output_file_info.keys():
        assert "//" not in an_export_filename
    export_filename = next(
        f for f in export.output_file_info.keys() if f.endswith("tar.gz") or f.endswith("tar")
    )

    # Prepare import
    repo_c = ansible_repo_factory()
    repo_d = ansible_repo_factory()
    repo_mapping = {repo_a.name: repo_c.name, repo_b.name: repo_d.name}
    importer = gen_object_with_cleanup(
        importers_pulp_api_client, {"name": str(uuid.uuid4()), "repo_mapping": repo_mapping}
    )

    # Import
    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    repo_c = ansible_repo_api_client.read(repo_c.pulp_href)
    repo_d = ansible_repo_api_client.read(repo_d.pulp_href)
    assert repo_c.latest_version_href == f"{repo_c.pulp_href}versions/1/"
    assert repo_d.latest_version_href == f"{repo_d.pulp_href}versions/1/"
    repo_ver_c = ansible_repo_version_api_client.read(f"{repo_c.pulp_href}versions/1/")
    repo_ver_d = ansible_repo_version_api_client.read(f"{repo_d.pulp_href}versions/1/")
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
    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    assert len(importers_pulp_imports_api_client.list(importer.pulp_href).results) == 2
    for repo in [repo_c, repo_d]:
        repo = ansible_repo_api_client.read(repo.pulp_href)
        # still only one version as pulp won't create a new version if nothing changed
        assert repo.latest_version_href == f"{repo.pulp_href}versions/1/"
