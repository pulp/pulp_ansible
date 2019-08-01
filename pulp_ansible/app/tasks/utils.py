import json

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from aiohttp import ClientSession


async def get_json_from_url(url):
    """Asynchronously get the json from request."""
    async with ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data


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
