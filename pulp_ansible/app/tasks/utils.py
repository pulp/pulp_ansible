from gettext import gettext as _
from collections import namedtuple
import logging
import json
import re
import yaml
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from rest_framework.serializers import ValidationError
from yaml.error import YAMLError

from pulp_ansible.app.constants import PAGE_SIZE

log = logging.getLogger(__name__)


def get_api_version(url):
    """Get API version."""
    result = re.findall(r"/v(\d)/", url)
    if len(result) == 0:
        raise RuntimeError(f"Could not determine API version for: {url}")
    return int(result[0])


def get_page_url(url, api_version, page=1):
    """Get URL page."""
    parsed_url = urlparse(url)
    new_query = parse_qs(parsed_url.query)

    if api_version < 3:
        new_query["page"] = page
        new_query["page_size"] = PAGE_SIZE
    else:
        new_query["offset"] = (page - 1) * PAGE_SIZE
        new_query["limit"] = PAGE_SIZE

    return urlunparse(parsed_url._replace(query=urlencode(new_query, doseq=True)))


def parse_metadata(download_result):
    """Parses JSON file."""
    with open(download_result.path) as fd:
        return json.load(fd)


RequirementsFileEntry = namedtuple("RequirementsFileEntry", ["name", "version", "source"])


def parse_collections_requirements_file(requirements_file_string):
    """
    Parses an Ansible requirement.yml file and returns all the collections defined in it.

    The requirements file is in the form:
        ---
        collections:
        - namespace.collection
        - name: namespace.collection
            version: version identifier, multiple identifiers are separated by ','
            source: the URL or prededefined source name in ~/.ansible_galaxy
                    to pull the collection from

    Args:
        requirements_file_string (str): The string of the requirements file.

    Returns:
        list: A list of RequirementsFileEntry objects, each containing `name`, `version`, and
            `source`.

    Raises:
            rest_framework.serializers.ValidationError: if requirements is not a valid yaml.

    """
    collection_info = []

    if requirements_file_string:
        if isinstance(requirements_file_string, str):
            try:
                requirements = yaml.safe_load(requirements_file_string)
            except YAMLError as err:
                raise ValidationError(
                    _(
                        "Failed to parse the collection requirements yml: {file} "
                        "with the following error: {error}".format(
                            file=requirements_file_string, error=err
                        )
                    )
                )
        else:
            requirements = requirements_file_string

        if not isinstance(requirements, dict) or "collections" not in requirements:
            raise ValidationError(
                _(
                    "Expecting collections requirements file to be a dict with the key "
                    "collections that contains a list of collections to install."
                )
            )

        if not isinstance(requirements["collections"], list):
            raise ValidationError(
                _(
                    "Expecting collections requirements file to be a dict with the key "
                    "collections that contains a list of collections to install."
                )
            )

        for collection_req in requirements["collections"]:
            if isinstance(collection_req, dict):
                req_name = collection_req.get("name", None)
                if req_name is None:
                    raise ValidationError(
                        _("Collections requirement entry should contain the key name.")
                    )

                req_version = collection_req.get("version", "*")
                req_source = collection_req.get("source", None)

                entry = RequirementsFileEntry(name=req_name, version=req_version, source=req_source)
            else:
                entry = RequirementsFileEntry(name=collection_req, version="*", source=None)
            if "." not in entry.name:
                raise ValidationError(
                    _(
                        "Collections requirement entry should contain the collection name in the "
                        "format namespace.name"
                    )
                )
            collection_info.append(entry)

    return collection_info


def get_file_obj_from_tarball(tar, file_path, artifact_path, raise_exc=True):
    """
    Get file obj from tarball.

    Args:
        tar(tarfile): The tarball.
        file_path(str): The desired file.
        artifact_path(str): The artifact path.

    Keyword Args:
        raise_exc(bool): Whether or not raise exception.

    """
    log.info(
        _("Reading {file_path} from {artifact_path}").format(
            file_path=file_path, artifact_path=artifact_path
        )
    )

    for path in [file_path, f"./{file_path}"]:
        try:
            file_obj = tar.extractfile(path)
        except KeyError:
            file_obj = None
        else:
            break

    if not file_obj and raise_exc:
        raise FileNotFoundError(f"{file_path} not found")

    return file_obj
