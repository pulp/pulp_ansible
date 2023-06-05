"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""
from os import path
import subprocess
import pytest
from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_VERSION,
    GALAXY_ANSIBLE_BASE_URL,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote


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
        **gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=collection_requirements)
    )
    repo = ansible_repo_factory(remote=remote.pulp_href)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL()
    sync_response = ansible_repo_api_client.sync(repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)

    # Distribute
    return ansible_distribution_factory(repo)


def test_collection_download_count(
    ansible_dir_factory,
    galaxy_v3_collections_api_client,
    install_scenario_distribution,
    pulp_admin_user,
):
    """Test that the collection download counting functions."""
    with pulp_admin_user:
        collection_namespace = ANSIBLE_DEMO_COLLECTION.split(".")[0]
        collection_name = ANSIBLE_DEMO_COLLECTION.split(".")[1]
        collection_detail = galaxy_v3_collections_api_client.read(
            path=install_scenario_distribution.base_path,
            namespace=collection_namespace,
            name=collection_name,
        )

        collection_detail = galaxy_v3_collections_api_client.read(
            path=install_scenario_distribution.base_path,
            namespace=collection_namespace,
            name=collection_name,
        )
        # Collection is installed twice in cli.test_collection_install
        assert collection_detail.download_count == "2"

        temp_dir = str(
            ansible_dir_factory(install_scenario_distribution.client_url, pulp_admin_user)
        )

        cmd = [
            "ansible-galaxy",
            "collection",
            "install",
            f"{ANSIBLE_DEMO_COLLECTION}:{ANSIBLE_DEMO_COLLECTION_VERSION}",
            "-c",
            "-p",
            temp_dir,
        ]

        directory = "{}/ansible_collections/{}".format(
            temp_dir, ANSIBLE_DEMO_COLLECTION.replace(".", "/")
        )

        assert not path.exists(directory), "Directory {} already exists".format(directory)
        subprocess.run(cmd, cwd=temp_dir)
        assert path.exists(directory), "Could not find directory {}".format(directory)

        collection_detail = galaxy_v3_collections_api_client.read(
            path=install_scenario_distribution.base_path,
            namespace=collection_namespace,
            name=collection_name,
        )
        assert collection_detail.download_count == "3"

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

        collection_detail = galaxy_v3_collections_api_client.read(
            path=install_scenario_distribution.base_path,
            namespace=collection_namespace,
            name=collection_name,
        )
        assert collection_detail.download_count == "4"
