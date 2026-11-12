from django.http import QueryDict
from django.test import SimpleTestCase

from pulp_ansible.app.utils import (
    COLLECTION_VERSION_LARGE_FIELDS,
    get_collection_version_deferred_fields,
    get_deferred_fields,
)


class TestGetCollectionVersionDeferredFields(SimpleTestCase):
    """Test get_collection_version_deferred_fields."""

    def test_field_selection(self):
        """Large fields are deferred according to the request's field selection."""
        cases = (
            ("", list(COLLECTION_VERSION_LARGE_FIELDS)),
            ("fields=docs_blob", ["files", "manifest", "contents"]),
            ("fields=", []),
            ("exclude_fields=docs_blob,files", ["docs_blob", "files"]),
            ("exclude_fields=", []),
            (
                "fields=docs_blob,files&exclude_fields=docs_blob",
                ["docs_blob", "manifest", "contents"],
            ),
        )
        for query_string, expected in cases:
            with self.subTest(query_string=query_string):
                self.assertEqual(
                    get_collection_version_deferred_fields(QueryDict(query_string)), expected
                )


class TestGetDeferredFields(SimpleTestCase):
    """Test get_deferred_fields."""

    def test_field_selection(self):
        """Fields are deferred according to the request's field selection."""
        cases = (
            ("", []),
            ("fields=a", ["b"]),
            ("fields=", []),
            ("exclude_fields=a", ["a"]),
        )
        for query_string, expected in cases:
            with self.subTest(query_string=query_string):
                self.assertEqual(get_deferred_fields(QueryDict(query_string), ("a", "b")), expected)
