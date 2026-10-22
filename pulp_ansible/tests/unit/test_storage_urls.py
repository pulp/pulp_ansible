from unittest import mock

import pytest

from pulp_ansible.app.tasks.utils import get_collection_import_url

ARCHIVE_HEADERS = {"Content-Disposition": "attachment;filename=archive.tar.gz"}


@pytest.mark.parametrize("url", ["https://storage.example/archive.tar.gz", None])
def test_collection_import_url_sets_archive_filename(url):
    """Both import paths share the same provider-neutral download filename."""
    artifact_file = object()
    with mock.patch(
        "pulp_ansible.app.tasks.utils.get_direct_storage_url", return_value=url
    ) as direct:
        assert get_collection_import_url(artifact_file) == url
    direct.assert_called_once_with(artifact_file, headers=ARCHIVE_HEADERS)
