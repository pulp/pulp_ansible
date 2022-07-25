"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""
import pytest

from pulp_ansible.tests.functional.utils import gen_ansible_remote, monitor_task
from pulp_ansible.tests.functional.constants import TEST_COLLECTION_CONFIGS
from orionutils.generator import build_collection


@pytest.fixture
def sync_and_count(sync_and_count_factory):
    """A helper fixture to perform a sync and check the count of Collections syned."""

    yield sync_and_count_factory("collection")


@pytest.mark.parallel
def test_sync_supports_mirror_option_true(sync_and_count, ansible_repo):
    """Sync multiple remotes into the same repo with mirror as `True`."""
    body_a = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    body_b = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    version_one_count = sync_and_count(body_a, repo=ansible_repo)
    version_two_count = sync_and_count(body_b, repo=ansible_repo, mirror=True)

    # Assert more CollectionVersion are present in the first sync than the second
    assert version_two_count == 1

    if ansible_repo.retain_repo_versions is None or ansible_repo.retain_repo_versions > 1:
        assert version_one_count > version_two_count


@pytest.mark.parallel
def test_sync_supports_mirror_option_false(sync_and_count, ansible_repo):
    """Sync multiple remotes into the same repo with mirror as `False`."""
    body_a = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    body_b = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    version_one_count = sync_and_count(body_a, repo=ansible_repo)
    version_two_count = sync_and_count(body_b, repo=ansible_repo, mirror=False)

    # Assert more CollectionVersion are present in the second sync than the first
    assert version_two_count >= 4

    if ansible_repo.retain_repo_versions is None or ansible_repo.retain_repo_versions > 1:
        assert version_one_count < version_two_count


@pytest.mark.parallel
def test_sync_mirror_defaults_to_false(sync_and_count, ansible_repo):
    """Sync multiple remotes into the same repo to ensure mirror defaults to `False`."""
    body_a = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - robertdebock.ansible_development_environment",
        sync_dependencies=False,
    )

    body_b = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - testing.k8s_demo_collection",
        sync_dependencies=False,
    )

    version_one_count = sync_and_count(body_a, repo=ansible_repo)
    version_two_count = sync_and_count(body_b, repo=ansible_repo)

    # Assert more CollectionVersion are present in the second sync than the first
    assert version_two_count >= 4

    if ansible_repo.retain_repo_versions is None or ansible_repo.retain_repo_versions > 1:
        assert version_one_count < version_two_count


@pytest.mark.parallel
def test_sync_collection_with_long_tag(sync_and_count):
    """Sync a collection that is known to have "longer" tag information."""
    body = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - ibm.ibm_zos_core",
        sync_dependencies=False,
    )
    count = sync_and_count(body)

    assert count >= 14


@pytest.mark.parallel
def test_sync_collection_with_dot_slash_in_manifest(sync_and_count):
    """Sync a collection that has a ./Manifest.json instead of Manifest.json."""
    body = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - rshad.collection_demo",
        sync_dependencies=False,
    )
    count = sync_and_count(body)

    assert count >= 6


@pytest.mark.parallel
def test_sync_collection_with_stranger_version_numbers_to_check_comparisons(sync_and_count):
    """Sync a collection that has strange version numbers and ensure it syncs correctly."""
    body = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - brightcomputing.bcm",
        sync_dependencies=False,
    )
    count = sync_and_count(body)
    assert count >= 5


@pytest.mark.parallel
class FullDependenciesSync:
    """
    Collection sync tests for syncing collections and their dependencies.

    Dependency Trees:
    A               E
    |             /   \
    B            F     G
    |            |     |
    C         H(1-3)   D
    |
    D

    H has 5 versions, no dependencies
    """

    @pytest.fixture(scope="class", autouse=True)
    def populated_distro(
        self, ansible_repo, ansible_distribution_factory, ansible_collection_version_api_client
    ):
        """Builds and publishes the collections to be used in this test."""
        distro = ansible_distribution_factory(ansible_repo)
        for cfg in TEST_COLLECTION_CONFIGS:
            collection = build_collection("skeleton", config=cfg)
            response = ansible_collection_version_api_client.create(
                collection.name,
                collection.namespace,
                collection.version,
                file=collection.filename,
                repository=ansible_repo.pulp_href,
            )
            monitor_task(response.task)
        return distro

    def test_simple_one_level_dependency(self, populated_distro, sync_and_count):
        """Sync test.c which requires test.d."""
        body = gen_ansible_remote(
            url=populated_distro.client_url,
            requirements_file="collections:\n  - test.c",
            include_pulp_auth=True,
        )
        count = sync_and_count(body)
        assert count == 2

    def test_simple_multi_level_dependency(self, populated_distro, sync_and_count):
        """Sync test.a which should get the dependency chain: test.b -> test.c -> test.d."""
        body = gen_ansible_remote(
            url=populated_distro.client_url,
            requirements_file="collections:\n  - test.a",
            include_pulp_auth=True,
        )
        count = sync_and_count(body)
        assert count == 4

    def test_complex_one_level_dependency(self, populated_distro):
        """Sync test.f which should get 3 versions of test.h."""
        body = gen_ansible_remote(
            url=populated_distro.client_url,
            requirements_file="collections:\n  - test.f",
            include_pulp_auth=True,
        )
        count = sync_and_count(body)
        assert count == 4

    def test_complex_multi_level_dependency(self, populated_distro, sync_and_count):
        """Sync test.e which should get test.f, test.d, test.g and 3 versions of test.h."""
        body = gen_ansible_remote(
            url=populated_distro,
            requirements_file="collections:\n  - test.e",
            include_pulp_auth=True,
        )
        count = sync_and_count(body)
        assert count == 7


@pytest.mark.nightly  # This test takes more than 4 minutes, a large sync
@pytest.mark.parallel
def test_v2_simple_dependency(sync_and_count, ansible_repo, ansible_collection_version_api_client):
    """Checks that the dependency resolution works on v2 api codepath."""
    body = gen_ansible_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - pulp.pulp_installer",
    )
    total_count = sync_and_count(body, repo=ansible_repo)

    posix = ansible_collection_version_api_client.list(
        repository_version=f"{ansible_repo.pulp_href}versions/1/", name="posix"
    )
    assert 0 < posix.count < total_count
