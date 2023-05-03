from os import path
import subprocess
import pytest

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL
from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_VERSION,
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
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
):
    """Prepare a distribution to install from."""
    remote = ansible_collection_remote_factory(
        **gen_ansible_remote(url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS)
    )
    repo = ansible_repo_factory(remote=remote.pulp_href)

    # Sync
    repository_sync_data = AnsibleRepositorySyncURL()
    sync_response = ansible_repo_api_client.sync(repo.pulp_href, repository_sync_data)
    monitor_task(sync_response.task)

    # Distribute
    return ansible_distribution_factory(repo)


def get_download_count(dl_count_api_client, namespace, name, distro_base_path, path, version):
    return dl_count_api_client.read(
        namespace=namespace,
        name=name,
        distro_base_path=distro_base_path,
        path=distro_base_path,
        version=version,
    ).download_count


def test_cv_download_count(
    galaxy_v3_content_collections_index_versions_download_count_api_client,
    install_scenario_distribution,
    pulp_admin_user,
    ansible_dir_factory,
):
    pass
    collection_name = ANSIBLE_DEMO_COLLECTION
    namespace, name = ANSIBLE_DEMO_COLLECTION.split(".")
    distro_base_path = install_scenario_distribution.base_path
    dl_count_api_client = galaxy_v3_content_collections_index_versions_download_count_api_client
    with pulp_admin_user:
        assert (
            get_download_count(
                dl_count_api_client=dl_count_api_client,
                namespace=namespace,
                name=name,
                distro_base_path=distro_base_path,
                path=distro_base_path,
                version=ANSIBLE_DEMO_COLLECTION_VERSION,
            )
            == 0
        )

        temp_dir = str(
            ansible_dir_factory(install_scenario_distribution.client_url, pulp_admin_user)
        )

        cmd = [
            "ansible-galaxy",
            "collection",
            "install",
            ANSIBLE_DEMO_COLLECTION,
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

        assert (
            get_download_count(
                dl_count_api_client=dl_count_api_client,
                namespace=namespace,
                name=name,
                distro_base_path=distro_base_path,
                path=distro_base_path,
                version=ANSIBLE_DEMO_COLLECTION_VERSION,
            )
            == 1
        )

        # Update command to install a second time
        cmd = [
            "ansible-galaxy",
            "collection",
            "install",
            collection_name,
            "-c",
            "-f",
            "-p",
            temp_dir,
        ]

        assert path.exists(directory)
        subprocess.run(cmd, cwd=temp_dir)
        assert (
            get_download_count(
                dl_count_api_client=dl_count_api_client,
                namespace=namespace,
                name=name,
                distro_base_path=distro_base_path,
                path=distro_base_path,
                version=ANSIBLE_DEMO_COLLECTION_VERSION,
            )
            == 2
        )
