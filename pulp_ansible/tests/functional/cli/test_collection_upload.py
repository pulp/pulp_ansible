"""Tests that Collections can be uploaded to  Pulp with the ansible-galaxy CLI."""

import pytest
import random
import string
import subprocess


@pytest.mark.parallel
def test_upload_collection(
    ansible_repo_api_client,
    galaxy_v3_collections_api_client,
    galaxy_v3_collection_versions_api_client,
    ansible_repo_factory,
    ansible_distribution_factory,
    ansible_dir_factory,
    wait_tasks,
):
    """Test whether ansible-galaxy can upload a Collection to Pulp."""
    repository = ansible_repo_factory()
    distribution = ansible_distribution_factory(repository=repository)
    ansible_dir = ansible_dir_factory(distribution.client_url)

    collection_name = "".join(random.choices(string.ascii_lowercase, k=26))
    subprocess.run(
        (
            "ansible-galaxy",
            "collection",
            "init",
            "--init-path",
            ansible_dir,
            f"pulp.{collection_name}",
        ),
        cwd=ansible_dir,
        check=True,
    )

    collection_meta = ansible_dir / "pulp" / collection_name / "meta"
    collection_meta.mkdir()
    runtime_yml = collection_meta / "runtime.yml"
    runtime_yml.write_text('requires_ansible: ">=2.9"\n')

    subprocess.run(
        (
            "ansible-galaxy",
            "collection",
            "build",
            "--output-path",
            ansible_dir,
            ansible_dir / "pulp" / collection_name,
        ),
        cwd=ansible_dir,
        check=True,
    )

    assert repository.latest_version_href.endswith("/0/")
    collections = galaxy_v3_collections_api_client.list(distribution.base_path)
    assert collections.meta.count == 0

    subprocess.run(
        (
            "ansible-galaxy",
            "collection",
            "publish",
            "-c",
            ansible_dir / f"pulp-{collection_name}-1.0.0.tar.gz",
        ),
        cwd=ansible_dir,
        check=True,
    )
    wait_tasks(repository.pulp_href)

    repository = ansible_repo_api_client.read(repository.pulp_href)
    assert repository.latest_version_href.endswith("/1/")
    collections = galaxy_v3_collections_api_client.list(distribution.base_path)
    assert collections.meta.count == 1  # We uploaded 1 collection
    version = galaxy_v3_collection_versions_api_client.read(
        collection_name, "pulp", distribution.base_path, "1.0.0"
    )
    assert version.requires_ansible == ">=2.9"
