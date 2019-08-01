import json

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def get_page_url(url, page=1):
    """Get URL page."""
    parsed_url = urlparse(url)
    new_query = parse_qs(parsed_url.query)
    new_query["page"] = page
    return urlunparse(parsed_url._replace(query=urlencode(new_query, doseq=True)))


def parse_metadata(download_result):
    """Parses JSON file."""
    with open(download_result.path) as fd:
        return json.load(fd)


def filter_namespace(metadata, url):
    """
    Filter namespace.

    filtering namespace for speeding up the tests, while issue:
    https://github.com/ansible/galaxy/issues/1974
    is not addressed
    """
    parsed_url = urlparse(url)
    new_query = parse_qs(parsed_url.query)

    namespace = new_query.get("namespace__name")

    if namespace and metadata.get("results"):
        results = []
        for result in metadata["results"]:
            if [result["namespace"]["name"]] == namespace:
                results.append(result)

        metadata["results"] = results

    return metadata
