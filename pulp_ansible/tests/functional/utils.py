"""Utilities for tests for the ansible plugin."""

import random
import string
from urllib.parse import urlparse, parse_qs

from pulp_smash import config
from pulp_smash.pulp3.utils import (
    gen_remote,
)

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_FIXTURE_URL,
)


cfg = config.get_config()


def randstr():
    return "".join(random.choices(string.ascii_lowercase, k=8))


def content_counts(repository_version, summary_type="present"):
    content_summary = getattr(repository_version.content_summary, summary_type)
    return {key: value["count"] for key, value in content_summary.items()}


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
