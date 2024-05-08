"""Tests collection sync functionality that is common to both Galaxy V2 and V3."""

import pytest
import subprocess


@pytest.fixture
def sync_and_count(
    ansible_repo_factory,
    ansible_git_remote_factory,
    ansible_sync_factory,
    ansible_collection_version_api_client,
):
    """A helper fixture to perform a sync and return the count in the repo now."""

    def _sync_and_count(remote_body, repo=None, **sync_kwargs):
        if repo is None:
            repo = ansible_repo_factory()
        previous_latest = repo.latest_version_href
        remote = ansible_git_remote_factory(**remote_body)
        sync_kwargs.update({"remote": remote.pulp_href})
        repo = ansible_sync_factory(repo, **sync_kwargs)
        assert repo.latest_version_href != previous_latest
        c = ansible_collection_version_api_client.list(repository_version=repo.latest_version_href)
        return c.count

    yield _sync_and_count


@pytest.mark.parallel
def test_sync_collection_from_git(
    sync_and_count,
    ansible_repo_factory,
    ansible_distribution_factory,
    gen_user,
    gen_object_with_cleanup,
    ansible_dir_factory,
):
    """Sync collections from Git repositories and then install one of them."""
    body = {
        "url": "https://github.com/pulp/pulp_installer.git",
        "include_pulp_auth": True,
    }

    repo = ansible_repo_factory()
    count = sync_and_count(body, repo=repo)
    assert count == 1

    count = sync_and_count(body, repo=repo)
    assert count == 1

    body = {"url": "https://github.com/pulp/squeezer.git"}
    count = sync_and_count(body, repo=repo)
    assert count == 2

    # Create a distribution.
    distribution = ansible_distribution_factory(repo)

    collection_name = "pulp.squeezer"

    ansible_dir = ansible_dir_factory(distribution.client_url)

    directory = ansible_dir / "ansible_collections" / collection_name.replace(".", "/")

    assert not directory.exists(), f"Directory {directory} already exists"

    # The install command needs --pre so a pre-release collection versions install
    subprocess.run(
        (
            "ansible-galaxy",
            "collection",
            "install",
            "--pre",
            collection_name,
            "-c",
            "-p",
            ansible_dir,
        ),
        cwd=ansible_dir,
        check=True,
    )

    assert directory.exists(), f"Could not find directory {directory}"


@pytest.mark.parallel
def test_sync_metadata_only_collection_from_git(
    ansible_repo,
    sync_and_count,
    ansible_distribution_factory,
    galaxy_v3_collection_versions_api_client,
):
    """Sync collections from Git repositories with metadata_only=True."""
    body = {
        "url": "https://github.com/ansible-collections/amazon.aws/",
        "metadata_only": True,
        "git_ref": "2.1.0",
    }
    count = sync_and_count(body, repo=ansible_repo)
    assert count == 1

    # Create a distribution.
    distribution = ansible_distribution_factory(ansible_repo)

    galaxy_v3_collection_versions_api_client.read("aws", "amazon", distribution.base_path, "2.1.0")


@pytest.mark.parallel
def test_sync_collection_from_git_commit_sha(
    ansible_repo,
    sync_and_count,
    ansible_distribution_factory,
    galaxy_v3_collection_versions_api_client,
):
    """Sync collections from Git repositories with git_ref that is a commit sha."""
    body = {
        "url": "https://github.com/ansible-collections/amazon.aws/",
        "metadata_only": True,
        "git_ref": "d0b54fc082cb63f63d34246c8fe668e19e74777c",
    }

    count = sync_and_count(body, repo=ansible_repo)
    assert count == 1

    # Create a distribution.
    distribution = ansible_distribution_factory(ansible_repo)

    version = galaxy_v3_collection_versions_api_client.read(
        "aws", "amazon", distribution.base_path, "1.5.1"
    )

    assert version.git_url == "https://github.com/ansible-collections/amazon.aws/"
    assert version.git_commit_sha == "d0b54fc082cb63f63d34246c8fe668e19e74777c"
    assert version.download_url is None


@pytest.mark.parallel
def test_sync_metadata_only_collection_from_pulp(
    ansible_sync_factory,
    ansible_repo_factory,
    ansible_distribution_factory,
    ansible_collection_version_api_client,
    ansible_git_remote_factory,
    ansible_collection_remote_factory,
):
    """Sync collections from another Pulp that only has metadata.

    Create a GitRemote
    Create a repository
    Sync from the remote
    Create distribution to serve the repository
    Create CollectionRemote pointing to the distribution.
    Create a second repository.
    Sync using the CollectionRemote into the second repository.
    Assert content is added to the second repository.

    """
    amazon_remote = ansible_git_remote_factory(
        url="https://github.com/ansible-collections/amazon.aws/",
        metadata_only=True,
        git_ref="2.1.0",
        include_pulp_auth=True,
    )

    first_repo = ansible_repo_factory()
    first_repo = ansible_sync_factory(first_repo, remote=amazon_remote.pulp_href)

    content = ansible_collection_version_api_client.list(
        repository_version=first_repo.latest_version_href
    )
    assert content.count == 1

    # Create a distribution.
    distribution = ansible_distribution_factory(first_repo)

    requirements_file = "collections:\n  - amazon.aws"
    second_remote = ansible_collection_remote_factory(
        url=distribution.client_url,
        requirements_file=requirements_file,
        sync_dependencies=False,
        include_pulp_auth=True,
    )

    second_repo = ansible_repo_factory(remote=second_remote.pulp_href)
    second_repo = ansible_sync_factory(second_repo)

    first_content = ansible_collection_version_api_client.list(
        repository_version=f"{first_repo.pulp_href}versions/1/"
    )
    assert first_content.count >= 1
    second_content = ansible_collection_version_api_client.list(
        repository_version=f"{second_repo.pulp_href}versions/1/"
    )
    assert second_content.count >= 1
