"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""

import subprocess
import pytest
from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_VERSION,
    GALAXY_ANSIBLE_BASE_URL,
)


@pytest.fixture
def install_scenario_distribution(
    delete_orphans_pre,
    ansible_repo_api_client,
    ansible_repo_factory,
    ansible_collection_remote_factory,
    ansible_distribution_factory,
    monitor_task,
):
    """Prepare a distribution to install from."""
    collection_requirements = f"collections:\n  - {ANSIBLE_DEMO_COLLECTION}"
    remote = ansible_collection_remote_factory(
        url=GALAXY_ANSIBLE_BASE_URL, requirements_file=collection_requirements
    )
    repo = ansible_repo_factory(remote=remote.pulp_href)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL()
    sync_response = ansible_repo_api_client.sync(repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)

    # Distribute
    return ansible_distribution_factory(repo)


def get_current_download_count(api_client, path, namespace, name):
    return int(
        api_client.read(
            path=path,
            namespace=namespace,
            name=name,
        ).download_count
    )


def test_collection_download_count(
    ansible_dir_factory,
    galaxy_v3_collections_api_client,
    install_scenario_distribution,
    pulp_settings,
):
    """Test that the collection download counting functions."""
    if not pulp_settings.ANSIBLE_COLLECT_DOWNLOAD_COUNT:
        pytest.skip("ANSIBLE_COLLECT_DOWNLOAD_COUNT not enabled")

    collection_namespace = ANSIBLE_DEMO_COLLECTION.split(".")[0]
    collection_name = ANSIBLE_DEMO_COLLECTION.split(".")[1]
    download_count = get_current_download_count(
        api_client=galaxy_v3_collections_api_client,
        path=install_scenario_distribution.base_path,
        namespace=collection_namespace,
        name=collection_name,
    )

    temp_dir = ansible_dir_factory(install_scenario_distribution.client_url)

    cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        f"{ANSIBLE_DEMO_COLLECTION}:{ANSIBLE_DEMO_COLLECTION_VERSION}",
        "-c",
        "-p",
        temp_dir,
    ]

    directory = temp_dir / "ansible_collections" / ANSIBLE_DEMO_COLLECTION.replace(".", "/")

    assert not directory.exists(), "Directory {} already exists".format(directory)
    subprocess.run(cmd, cwd=temp_dir)
    assert directory.exists(), "Could not find directory {}".format(directory)

    assert (download_count + 1) == get_current_download_count(
        api_client=galaxy_v3_collections_api_client,
        path=install_scenario_distribution.base_path,
        namespace=collection_namespace,
        name=collection_name,
    )

    # TODO update to use a second collection version when available
    cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        f"{ANSIBLE_DEMO_COLLECTION}:{ANSIBLE_DEMO_COLLECTION_VERSION}",
        "-c",
        "-f",
        "-p",
        temp_dir,
    ]

    subprocess.run(cmd, cwd=temp_dir)

    assert (download_count + 2) == get_current_download_count(
        api_client=galaxy_v3_collections_api_client,
        path=install_scenario_distribution.base_path,
        namespace=collection_namespace,
        name=collection_name,
    )
