# coding=utf-8
"""Utilities for tests for the ansible plugin."""
from functools import partial
from unittest import SkipTest
from time import sleep

from pulp_smash import api, config, selectors
from pulp_smash.pulp3.utils import (
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
from pulpcore.client.pulp_ansible import ApiClient as AnsibleApiClient


cfg = config.get_config()
configuration = cfg.get_bindings_config()


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_ansible isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({"pulp_ansible"}, SkipTest)


def gen_ansible_client():
    """Return an OBJECT for ansible client."""
    return AnsibleApiClient(configuration)


def gen_ansible_remote(url=ANSIBLE_FIXTURE_URL, **kwargs):
    """Return a semi-random dict for use in creating a ansible Remote.

    :param url: The URL of an external content source.
    """
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


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""


core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)


def monitor_task(task_href):
    """Polls the Task API until the task is in a completed state.

    Prints the task details and a success or failure message. Exits on failure.

    Args:
        task_href(str): The href of the task to monitor

    Returns:
        list[str]: List of hrefs that identify resource created by the task

    """
    completed = ["completed", "failed", "canceled"]
    task = tasks.read(task_href)
    while task.state not in completed:
        sleep(1)
        task = tasks.read(task_href)

    if task.state == "completed":
        return task.created_resources

    return task.to_dict()


def wait_tasks():
    """Polls the Task API until all tasks are in a completed state."""
    running_tasks = tasks.list(state="running")
    while running_tasks.count:
        sleep(1)
        running_tasks = tasks.list(state="running")
