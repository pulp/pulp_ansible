"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""

import json
from os import path
import subprocess
import pytest

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DEMO_COLLECTION,
    ANSIBLE_DEMO_COLLECTION_VERSION,
    ANSIBLE_DEMO_COLLECTION_REQUIREMENTS as DEMO_REQUIREMENTS,
    GALAXY_ANSIBLE_BASE_URL,
)


@pytest.fixture
def install_scenario_distribution(
    ansible_sync_factory,
    ansible_collection_remote_factory,
    ansible_distribution_factory,
):
    """Prepare a distribution to install from."""
    remote = ansible_collection_remote_factory(
        url=GALAXY_ANSIBLE_BASE_URL, requirements_file=DEMO_REQUIREMENTS
    )
    repo = ansible_sync_factory(remote=remote.pulp_href)
    return ansible_distribution_factory(repo)


# Do not mark this test parallel, because we need to assert that the last dl log is ours.
def test_install_collection(install_scenario_distribution, ansible_dir_factory, pulp_settings):
    """Test that the collection can be installed from Pulp."""
    if not pulp_settings.ANSIBLE_COLLECT_DOWNLOAD_LOG:
        pytest.skip("ANSIBLE_COLLECT_DOWNLOAD_LOG not enabled")

    collection_name = ANSIBLE_DEMO_COLLECTION
    collection_version = ANSIBLE_DEMO_COLLECTION_VERSION

    temp_dir = str(ansible_dir_factory(install_scenario_distribution.client_url))

    directory = "{}/ansible_collections/{}".format(temp_dir, collection_name.replace(".", "/"))

    assert not path.exists(directory), "Directory {} already exists".format(directory)
    subprocess.run(
        (
            "ansible-galaxy",
            "collection",
            "install",
            collection_name,
            "-c",
            "-p",
            temp_dir,
        ),
        cwd=temp_dir,
        check=True,
    )

    assert path.exists(directory), "Could not find directory {}".format(directory)
    dl_log_dump = subprocess.check_output(["pulpcore-manager", "download-log"])
    dl_log = json.loads(dl_log_dump)
    assert (
        dl_log[-1]["content_unit"] == f"<CollectionVersion: {collection_name} {collection_version}>"
    )
    assert dl_log[-1]["user"] == "admin"


@pytest.mark.parallel
def test_install_signed_collection(
    ansible_repo_api_client,
    install_scenario_distribution,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
    gen_user,
    ansible_dir_factory,
    monitor_task,
):
    """Test that the collection can be installed from Pulp."""
    user = gen_user(model_roles=["ansible.ansiblerepository_owner"])
    with user:
        collection_name = ANSIBLE_DEMO_COLLECTION
        repository_href = install_scenario_distribution.repository
        signing_service = ascii_armored_detached_signing_service
        # Switch this over to signature upload in the future
        signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}
        monitor_task(ansible_repo_api_client.sign(repository_href, signing_body).task)

        ansible_dir = ansible_dir_factory(install_scenario_distribution.client_url)

        directory = ansible_dir / "ansible_collections" / collection_name.replace(".", "/")

        assert not path.exists(directory), "Directory {} already exists".format(directory)
        subprocess.run(
            (
                "ansible-galaxy",
                "collection",
                "install",
                collection_name,
                "-c",
                "-p",
                ansible_dir,
                "--keyring",
                f"{signing_gpg_homedir_path}/pubring.kbx",
            ),
            cwd=ansible_dir,
            check=True,
        )
        assert path.exists(directory), "Could not find directory {}".format(directory)
