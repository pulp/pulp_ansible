"""Utilities for tests for the ansible plugin."""

import random
import string
from urllib.parse import urlparse, parse_qs

from pulp_smash import config
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_remote,
    gen_repo,
)

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_FIXTURE_URL,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    TasksApi,
    StatusApi,
)
from pulpcore.client.pulp_ansible import (
    ApiClient as AnsibleApiClient,
    ContentCollectionVersionsApi,
    DistributionsAnsibleApi,
    PulpAnsibleApiV3CollectionsApi,
    PulpAnsibleApiV3CollectionsVersionsApi,
    RepositoriesAnsibleApi,
    RemotesCollectionApi,
    RemotesGitApi,
    RemotesRoleApi,
    AnsibleRepositorySyncURL,
    RepositoriesAnsibleVersionsApi,
)


cfg = config.get_config()
configuration = cfg.get_bindings_config()


def randstr():
    return "".join(random.choices(string.ascii_lowercase, k=8))


def is_galaxy_ng_installed():
    """Returns whether or not the galaxy_ng plugin is installed."""
    configuration = cfg.get_bindings_config()
    core_client = CoreApiClient(configuration)
    status_client = StatusApi(core_client)

    status = status_client.status_read()

    for plugin in status.versions:
        if plugin.component == "galaxy":
            return True
    return False


def content_counts(repository_version, summary_type="present"):
    content_summary = getattr(repository_version.content_summary, summary_type)
    return {key: value["count"] for key, value in content_summary.items()}


def gen_ansible_client():
    """Return an OBJECT for ansible client."""
    return AnsibleApiClient(configuration)


def gen_ansible_remote(url=ANSIBLE_FIXTURE_URL, include_pulp_auth=False, **kwargs):
    """Return a semi-random dict for use in creating a ansible Remote.

    :param url: The URL of an external content source.
    """
    if include_pulp_auth:
        kwargs["username"] = cfg.pulp_auth[0]
        kwargs["password"] = cfg.pulp_auth[1]

    if "rate_limit" not in kwargs:
        kwargs["rate_limit"] = 5

    return gen_remote(url, **kwargs)


core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)


class TestCaseUsingBindings(PulpTestCase):
    """A parent TestCase that instantiates the various bindings used throughout tests."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
        cls.repo_version_api = RepositoriesAnsibleVersionsApi(cls.client)
        cls.remote_collection_api = RemotesCollectionApi(cls.client)
        cls.remote_git_api = RemotesGitApi(cls.client)
        cls.remote_role_api = RemotesRoleApi(cls.client)
        cls.distributions_api = DistributionsAnsibleApi(cls.client)
        cls.cv_api = ContentCollectionVersionsApi(cls.client)
        cls.collections_v3api = PulpAnsibleApiV3CollectionsApi(cls.client)
        cls.collections_versions_v3api = PulpAnsibleApiV3CollectionsVersionsApi(cls.client)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans()


class SyncHelpersMixin:
    """A common place for sync helper functions."""

    def _create_repo_and_sync_with_remote(self, remote, distribution=False, **repo_kwargs):
        """
        Create a repository and then sync with the provided `remote`.

        Args:
            remote: The remote to be sync with

        Returns:
            repository: The created repository object to be asserted to.
        """
        # Create the repository.
        repo = self.repo_api.create(gen_repo(**repo_kwargs))
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        if distribution:
            self._create_distribution_from_repo(repo)
        return self._sync_repo(repo, remote=remote.pulp_href)

    def _create_repo_with_attached_remote_and_sync(self, remote, **repo_kwargs):
        """
        Create a repository with the remote attached, and then sync without specifying the `remote`.

        Args:
            remote: The remote to attach to the repository

        Returns:
            repository: The created repository object to be asserted to.
        """
        # Create the repository.
        repo = self.repo_api.create(gen_repo(remote=remote.pulp_href, **repo_kwargs))
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return self._sync_repo(repo)

    def _sync_repo(self, repo, **kwargs):
        """
        Sync the repo with optional `kwarg` parameters passed on to the sync method.

        Args:
            repo: The repository to sync

        Returns:
            repository: The updated repository after the sync is complete
        """
        repository_sync_data = AnsibleRepositorySyncURL(**kwargs)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)
        return repo

    def _create_distribution_from_repo(self, repo, cleanup=True):
        """
        Create an `AnsibleDistribution` serving the `repo` with the `base_path`.

        Args:
            repo: The repository to serve with the `AnsibleDistribution`
            cleanup: Whether the distribution should be cleaned up

        Returns:
            The created `AnsibleDistribution`.
        """
        # Create a distribution.
        body = gen_distribution()
        body["repository"] = repo.pulp_href
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])
        if cleanup:
            self.addCleanup(self.distributions_api.delete, distribution.pulp_href)
        return distribution


def iterate_all(list_func, **kwargs):
    """
    Iterate through all of the items on every page in a paginated list view.
    """
    kwargs
    while kwargs is not None:
        response = list_func(**kwargs)

        for x in response.results:
            yield x

        if response.next:
            qs = parse_qs(urlparse(response.next).query)
            for param in ("offset", "limit"):
                if param in qs:
                    kwargs[param] = qs[param][0]
        else:
            kwargs = None
