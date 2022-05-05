"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""
import json
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


def test_install_collection(tmp_path, install_scenario_distribution):
    """Test that the collection can be installed from Pulp."""
    collection_name = ANSIBLE_DEMO_COLLECTION
    collection_version = ANSIBLE_DEMO_COLLECTION_VERSION

    temp_dir = str(tmp_path)
    cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        collection_name,
        "-c",
        "-s",
        install_scenario_distribution.client_url,
        "-p",
        temp_dir,
    ]

    directory = "{}/ansible_collections/{}".format(temp_dir, collection_name.replace(".", "/"))

    assert not path.exists(directory), "Directory {} already exists".format(directory)
    subprocess.run(cmd)
    assert path.exists(directory), "Could not find directory {}".format(directory)
    dl_log_dump = subprocess.check_output(["pulpcore-manager", "download-log"])
    dl_log = json.loads(dl_log_dump)
    assert (
        dl_log[-1]["content_unit"] == f"<CollectionVersion: {collection_name} {collection_version}>"
    )
    assert dl_log[-1]["user"] == "admin"


def test_install_signed_collection(
    tmp_path,
    ansible_repo_api_client,
    install_scenario_distribution,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
):
    """Test that the collection can be installed from Pulp."""
    collection_name = ANSIBLE_DEMO_COLLECTION
    repository_href = install_scenario_distribution.repository
    signing_service = ascii_armored_detached_signing_service
    # Switch this over to signature upload in the future
    signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}
    monitor_task(ansible_repo_api_client.sign(repository_href, signing_body).task)

    temp_dir = str(tmp_path)
    cmd = [
        "ansible-galaxy",
        "collection",
        "install",
        collection_name,
        "-c",
        "-s",
        install_scenario_distribution.client_url,
        "-p",
        temp_dir,
        "--keyring",
        f"{signing_gpg_homedir_path}/pubring.kbx",
    ]

    directory = "{}/ansible_collections/{}".format(temp_dir, collection_name.replace(".", "/"))

    assert not path.exists(directory), "Directory {} already exists".format(directory)
    subprocess.run(cmd)
    assert path.exists(directory), "Could not find directory {}".format(directory)
