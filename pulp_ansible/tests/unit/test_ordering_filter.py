from django.test import RequestFactory, TestCase

from pulp_ansible.app.galaxy.v3.filters import CollectionVersionSearchFilter
from pulp_ansible.app.models import AnsibleRepository, Collection, CollectionVersion
from pulp_ansible.app.models import CrossRepositoryCollectionVersionIndex as CVIndex

from .utils import randstr


class TestCollectionVersionSearchFilterOrdering(TestCase):
    """Verify that CollectionVersionSearchFilter produces deterministic ordering."""

    def _apply_filter(self, qs, params):
        """Run CollectionVersionSearchFilter against a queryset with the given query params."""
        request = RequestFactory().get("/", params)
        request.query_params = request.GET
        filterset = CollectionVersionSearchFilter(
            data=request.query_params,
            queryset=qs,
            request=request,
        )
        return filterset.qs

    def _build_index(self, specs):
        """Create CVIndex rows from a list of (namespace, name, version) specs."""
        repo = AnsibleRepository.objects.create(name=randstr())
        for namespace, name, version in specs:
            col, _ = Collection.objects.get_or_create(name=name)
            cv = CollectionVersion.objects.create(
                collection=col,
                sha256=randstr(),
                namespace=namespace,
                name=name,
                version=version,
            )
            CVIndex.objects.create(
                repository=repo,
                collection_version=cv,
                is_deprecated=False,
                is_signed=False,
                is_highest=False,
            )
        return CVIndex.objects.all()

    def test_order_by_name_ties_sorted_by_pk(self):
        """Ensure rows with the same name are sub-sorted by pk descending."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "samename", "1.0.0"),
                (ns, "samename", "2.0.0"),
                (ns, "samename", "3.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "name"})
        pks = list(qs.values_list("pk", flat=True))

        # StableOrderingFilter appends -pk (descending) as tiebreaker
        assert pks == sorted(pks, reverse=True)

    def test_order_by_name_groups_correctly(self):
        """Ensure ordering by name groups results alphabetically."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "charlie", "1.0.0"),
                (ns, "alpha", "1.0.0"),
                (ns, "bravo", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "name"})
        names = list(qs.values_list("collection_version__name", flat=True))

        assert names == ["alpha", "bravo", "charlie"]

    def test_order_by_name_desc_groups_correctly(self):
        """Ensure ordering by -name groups results in reverse alphabetical order."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "charlie", "1.0.0"),
                (ns, "alpha", "1.0.0"),
                (ns, "bravo", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "-name"})
        names = list(qs.values_list("collection_version__name", flat=True))

        assert names == ["charlie", "bravo", "alpha"]

    def test_order_by_namespace_ties_sorted_by_pk(self):
        """Ensure rows with the same namespace are sub-sorted by pk descending."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "foo", "1.0.0"),
                (ns, "bar", "1.0.0"),
                (ns, "baz", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "namespace"})
        pks = list(qs.values_list("pk", flat=True))

        # StableOrderingFilter appends -pk (descending) as tiebreaker
        assert pks == sorted(pks, reverse=True)

    def test_order_by_version_semantic_ordering(self):
        """Ensure version ordering uses the semver collation correctly."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "col", "2.0.0"),
                (ns, "col", "1.10.0"),
                (ns, "col", "1.2.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "version"})
        versions = list(qs.values_list("collection_version__version", flat=True))

        # semver collation sorts numerically, not lexicographically
        assert versions == ["1.2.0", "1.10.0", "2.0.0"]

    def test_order_by_version_desc_semantic_ordering(self):
        """Ensure descending version ordering uses the semver collation correctly."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "col", "2.0.0"),
                (ns, "col", "1.10.0"),
                (ns, "col", "1.2.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "-version"})
        versions = list(qs.values_list("collection_version__version", flat=True))

        assert versions == ["2.0.0", "1.10.0", "1.2.0"]

    def test_order_by_version_ties_are_stable(self):
        """Ensure rows with the same version produce stable ordering."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "aaa", "1.0.0"),
                (ns, "bbb", "1.0.0"),
                (ns, "ccc", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "version"})
        first_run = list(qs.values_list("pk", flat=True))
        second_run = list(qs.values_list("pk", flat=True))

        assert first_run == second_run

    def test_no_order_by_still_has_stable_ordering(self):
        """Ensure a default stable ordering is applied even without order_by."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "foo", "1.0.0"),
                (ns, "bar", "1.0.0"),
                (ns, "baz", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {})
        first_run = list(qs.values_list("pk", flat=True))
        second_run = list(qs.values_list("pk", flat=True))

        assert first_run == second_run

    def test_order_by_name_returns_stable_results(self):
        """Ensure results ordered by name are stable across repeated evaluations."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "samename", "1.0.0"),
                (ns, "samename", "2.0.0"),
                (ns, "samename", "3.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"order_by": "name"})
        first_run = list(qs.values_list("pk", flat=True))
        second_run = list(qs.values_list("pk", flat=True))

        assert first_run == second_run

    def test_filter_by_name_with_ordering(self):
        """Ensure filtering by name combined with ordering works correctly."""
        ns = randstr()
        qs = self._build_index(
            [
                (ns, "target", "1.0.0"),
                (ns, "target", "2.0.0"),
                (ns, "other", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"name": "target", "order_by": "version"})
        versions = list(qs.values_list("collection_version__version", flat=True))

        assert versions == ["1.0.0", "2.0.0"]

    def test_filter_by_namespace_with_ordering(self):
        """Ensure filtering by namespace combined with ordering works correctly."""
        ns = randstr()
        other_ns = randstr()
        qs = self._build_index(
            [
                (ns, "bravo", "1.0.0"),
                (ns, "alpha", "1.0.0"),
                (other_ns, "charlie", "1.0.0"),
            ]
        )

        qs = self._apply_filter(qs, {"namespace": ns, "order_by": "name"})
        names = list(qs.values_list("collection_version__name", flat=True))

        assert names == ["alpha", "bravo"]
