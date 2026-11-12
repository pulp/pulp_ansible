from unittest import mock

from django.http import QueryDict
from django.test import TestCase

from pulpcore.plugin.util import get_domain

from pulp_ansible.app.utils import COLLECTION_VERSION_LARGE_FIELDS
from pulp_ansible.app.viewsets import CollectionVersionViewSet


class TestCollectionVersionViewSetQueryset(TestCase):
    """Test that CollectionVersionViewSet defers the large JSON fields."""

    def _view(self, method="GET", query_string=""):
        view = CollectionVersionViewSet()
        view.action = "list"
        view.request = mock.Mock(
            method=method, query_params=QueryDict(query_string), pulp_domain=get_domain()
        )
        return view

    def _deferred(self, method, query_string):
        deferred, defer = self._view(method, query_string).get_queryset().query.deferred_loading
        self.assertTrue(defer)
        return set(deferred)

    def test_deferred_fields(self):
        """The large JSON fields are deferred unless they are rendered."""
        cases = (
            ("GET", "", set(COLLECTION_VERSION_LARGE_FIELDS)),
            ("GET", "fields=docs_blob", set(COLLECTION_VERSION_LARGE_FIELDS) - {"docs_blob"}),
            ("HEAD", "", set(COLLECTION_VERSION_LARGE_FIELDS)),
            ("POST", "", set()),
        )
        for method, query_string, expected in cases:
            with self.subTest(method=method, query_string=query_string):
                self.assertEqual(self._deferred(method, query_string), expected)

    def test_artifact_prefetch(self):
        """Artifacts are prefetched only when a checksum field is rendered."""
        cases = (
            ("", True),
            ("fields=sha256", True),
            ("fields=pulp_href", False),
        )
        for query_string, expected in cases:
            with self.subTest(query_string=query_string):
                queryset = self._view(query_string=query_string).get_queryset()
                self.assertEqual("_artifacts" in queryset._prefetch_related_lookups, expected)
