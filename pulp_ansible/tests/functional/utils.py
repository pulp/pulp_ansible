"""Utilities for tests for the ansible plugin."""
from dynaconf import Dynaconf
from functools import partial
from time import sleep
import unittest

from pulp_smash import api, config, selectors
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_remote,
    gen_repo,
    gen_publisher,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
    sync,
)

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_ROLE_NAME,
    ANSIBLE_ROLE_CONTENT_PATH,
    ANSIBLE_FIXTURE_URL,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_REPO_PATH,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    TasksApi,
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
)


cfg = config.get_config()
configuration = cfg.get_bindings_config()


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_ansible isn't installed."""
    require_pulp_3(unittest.SkipTest)
    require_pulp_plugins({"ansible"}, unittest.SkipTest)


def gen_ansible_client():
    """Return an OBJECT for ansible client."""
    return AnsibleApiClient(configuration)


def gen_ansible_remote(url=ANSIBLE_FIXTURE_URL, **kwargs):
    """Return a semi-random dict for use in creating a ansible Remote.

    :param url: The URL of an external content source.
    """
    if "rate_limit" not in kwargs:
        kwargs["rate_limit"] = 5

    return gen_remote(url, **kwargs)


def gen_ansible_publisher(**kwargs):
    """Return a semi-random dict for use in creating a Remote.

    :param url: The URL of an external content source.
    """
    return gen_publisher(**kwargs)


def get_ansible_content_paths(repo):
    """Return the relative path of content units present in an ansible repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    # FIXME
    return [content_unit["relative_path"] for content_unit in get_content(repo)[ANSIBLE_ROLE_NAME]]


def gen_ansible_content_attrs(artifact):
    """Generate a dict with content unit attributes.

    :param: artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    # FIXME: add content specific metadata here
    return {"artifact": artifact["pulp_href"]}


def populate_pulp(cfg, url=ANSIBLE_FIXTURE_URL):
    """Add ansible contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp application.
    :param url: The ansible repository URL. Defaults to
        :data:`pulp_smash.constants.ANSIBLE_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one file content in Pulp.
    """
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(ANSIBLE_REMOTE_PATH, gen_ansible_remote(url)))
        repo.update(client.post(ANSIBLE_REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote["pulp_href"])
        if repo:
            client.delete(repo["pulp_href"])
    return client.get(ANSIBLE_ROLE_CONTENT_PATH)["results"]


skip_if = partial(selectors.skip_if, exc=unittest.SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""


core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)


def wait_tasks():
    """Polls the Task API until all tasks are in a completed state."""
    running_tasks = tasks.list(state="running")
    while running_tasks.count:
        sleep(1)
        running_tasks = tasks.list(state="running")


class TestCaseUsingBindings(PulpTestCase):
    """A parent TestCase that instantiates the various bindings used throughout tests."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = gen_ansible_client()
        cls.repo_api = RepositoriesAnsibleApi(cls.client)
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

    def _create_repo_and_sync_with_remote(self, remote, **repo_kwargs):
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

    def _create_empty_repo_and_distribution(self, cleanup=True):
        """
        Creates an empty `AnsibleRepository` and an `AnsibleDistribution` serving that repository.

        Args:
            cleanup: Whether the repository and distribution should be cleaned up

        Returns:
            Tuple of the created `AnsibleRepository`, `AnsibleDistribution`
        """
        repo = self.repo_api.create(gen_repo())
        if cleanup:
            self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return repo, self._create_distribution_from_repo(repo, cleanup=cleanup)


settings = Dynaconf(
    settings_files=["pulp_ansible/tests/assets/func_test_settings.py", "/etc/pulp/settings.py"]
)


def get_psql_smash_cmd(sql_statement):
    """
    Generate a command in a format for pulp smash cli client to execute the specified SQL statement.

    The implication is that PostgreSQL is always running on localhost.
    Args:
        sql_statement(str): An SQL statement to execute.
    Returns:
        tuple: a command in the format for  pulp smash cli client
    """
    host = "localhost"
    user = settings.DATABASES["default"]["USER"]
    password = settings.DATABASES["default"]["PASSWORD"]
    dbname = settings.DATABASES["default"]["NAME"]
    return ("psql", "-c", sql_statement, f"postgresql://{user}:{password}@{host}/{dbname}")
