"""Utilities for tests for the ansible plugin."""

import random
import string
from urllib.parse import urlparse, parse_qs


def randstr():
    return "".join(random.choices(string.ascii_lowercase, k=8))


def content_counts(repository_version, summary_type="present"):
    content_summary = getattr(repository_version.content_summary, summary_type)
    return {key: value["count"] for key, value in content_summary.items()}


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
