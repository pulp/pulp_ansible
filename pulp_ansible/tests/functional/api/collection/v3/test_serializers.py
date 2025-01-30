"""Tests related to Galaxy V3 serializers."""


def test_v3_updated_at(
    ansible_bindings,
    ansible_sync_factory,
    ansible_collection_remote_factory,
    ansible_distribution_factory,
):
    """Test Collections V3 endpoint field: ``updated_at``."""

    requirements1 = """
    collections:
        - name: "pulp.squeezer"
          version: "0.0.7"
    """

    requirements2 = """
    collections:
        - name: "pulp.squeezer"
          version: "0.0.17"
    """

    # sync the first version ...
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file=requirements1,
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)
    distribution = ansible_distribution_factory(repository=repository)

    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)

    original_highest_version = collections.data[0].highest_version["version"]
    original_updated_at = collections.data[0].updated_at

    original_total_versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        "squeezer", "pulp", distribution.base_path
    ).meta.count

    # sync the second version ...
    # Don't wait on the update task here. The sync will wait for us.
    ansible_bindings.RemotesCollectionApi.partial_update(
        remote.pulp_href, {"requirements_file": requirements2}
    )

    ansible_sync_factory(ansible_repo=repository, remote=remote.pulp_href, optimize=True)

    # enumerate new data after 2nd sync ...
    collections = ansible_bindings.PulpAnsibleApiV3CollectionsApi.list(distribution.base_path)
    highest_version = collections.data[0].highest_version["version"]
    updated_at = collections.data[0].updated_at
    total_versions = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.list(
        "squeezer", "pulp", distribution.base_path
    ).meta.count

    assert original_highest_version == "0.0.7"
    assert highest_version == "0.0.17"
    assert original_total_versions == 1
    assert total_versions == 2
    assert updated_at > original_updated_at


def test_v3_collection_version_from_synced_data(
    ansible_bindings,
    ansible_sync_factory,
    ansible_collection_remote_factory,
    ansible_distribution_factory,
):
    """Test Collection Versions V3 endpoint fields."""
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - name: cisco.nxos\n    version: 1.4.0",
        sync_dependencies=False,
    )

    repository = ansible_sync_factory(remote=remote.pulp_href)
    distribution = ansible_distribution_factory(repository=repository)

    version = ansible_bindings.PulpAnsibleApiV3CollectionsVersionsApi.read(
        "nxos", "cisco", distribution.base_path, "1.4.0"
    )

    assert version.requires_ansible == ">=2.9.10,<2.11"
    assert "'name': 'README.md'" in str(version.files)
    assert version.manifest["collection_info"]["name"] == "nxos"
