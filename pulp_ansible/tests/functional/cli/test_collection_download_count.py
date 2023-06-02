"""Tests that Collections hosted by Pulp can be installed by ansible-galaxy."""
from os import path
import subprocess
import pytest
from urllib.parse import urljoin

from pulpcore.client.pulp_ansible import AnsibleRepositorySyncURL
from pulp_smash import api, config
from pulp_smash.pulp3.bindings import monitor_task

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


@pytest.fixture(scope="session")
def pulp_client():
    """Create and configure a Pulp API client, including custom authentication headers."""
    cfg = config.get_config()
    client = api.Client(cfg)
    headers = cfg.custom.get("headers", None)
    if headers:
        client.request_kwargs.setdefault("headers", {}).update(headers)
    return client


def get_galaxy_url(base, path):
    """Given an Ansible Distribution base_path and an endpoint path, construct a URL.

    Takes the expected GALAXY_API_ROOT setting of the target into consideration.
    """
    cfg = config.get_config()
    path = path.lstrip("/")
    GALAXY_API_ROOT = cfg.custom.get(
        "galaxy_api_root", "/pulp_ansible/galaxy/%(base_path)s/api/"
    ) % {"base_path": base}
    return urljoin(GALAXY_API_ROOT, path)


def test_collection_download_count(
    install_scenario_distribution,
    pulp_admin_user,
    ansible_dir_factory,
    pulp_client,
):
    """Test that the collection download counting functions."""
    with pulp_admin_user:
        collection_namespace = ANSIBLE_DEMO_COLLECTION.split(".")[0]
        collection_name = ANSIBLE_DEMO_COLLECTION.split(".")[1]
        url = get_galaxy_url(
            install_scenario_distribution.base_path,
            f"/v3/collections/{collection_namespace}/{collection_name}/",
        )
        collection_detail = pulp_client.using_handler(api.json_handler).get(url)

        # Collection is installed twice in cli.test_collection_install
        assert collection_detail["download_count"] == 0

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

        collection_detail = pulp_client.using_handler(api.json_handler).get(url)
        assert collection_detail["download_count"] == 1

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

        collection_detail = pulp_client.using_handler(api.json_handler).get(url)
        assert collection_detail["download_count"] == 2
