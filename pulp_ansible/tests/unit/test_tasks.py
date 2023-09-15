from unittest import mock
from django.test import TestCase

from orionutils.generator import randstr

from pulp_ansible.app.models import AnsibleDistribution
from pulp_ansible.app.models import AnsibleRepository
from pulp_ansible.app.models import CollectionVersion

from pulp_ansible.app.tasks.collections import (
    _rebuild_collection_version_meta,
    rebuild_repository_collection_versions_metadata,
    _update_highest_version,
)

from .utils import build_cvs_from_specs


class TestCollectionReImport(TestCase):
    """Test Collection Re-Import."""

    def setUp(self):
        """Make all the test data."""

        specs = [
            ("foo", "bar", "1.0.0"),
            ("foo", "baz", "1.0.0"),
            ("zip", "drive", "1.0.0"),
        ]

        self.collection_versions = build_cvs_from_specs(specs)

        # create a repository
        self.repo = AnsibleRepository(name="foorepo")
        self.repo.save()

        # create the distro
        AnsibleDistribution.objects.create(
            name="foorepo", base_path="foorepo", repository=self.repo
        )

        # add the cvs to a repository version
        for cv in self.collection_versions:
            qs = CollectionVersion.objects.filter(pk=cv.pk)
            with self.repo.new_version() as new_version:
                new_version.add_content(qs)

    def test_reimport_single_cv_adds_docs(self):
        """Test that rebuild_collection adds docs to the collection."""
        this_cv = self.collection_versions[0]
        _rebuild_collection_version_meta(this_cv)
        cv = CollectionVersion.objects.get(pulp_id=this_cv.pk)
        assert cv.docs_blob["collection_readme"]["html"] == "<h1>title</h1>\n<p>collection docs</p>"

    @mock.patch("pulp_ansible.app.tasks.collections._rebuild_collection_version_meta")
    @mock.patch("pulp_ansible.app.tasks.collections.ProgressReport")
    def test_reimport_repository_rebuilds_all_collections(
        self, mock_progress_report, mock_rebuild_cv
    ):
        """Make sure each CV in the repo is rebuilt."""
        rebuild_repository_collection_versions_metadata(self.repo.latest_version().pk)

        # ensure the function was called once for each cv
        expected_cvs = self.collection_versions
        assert mock_rebuild_cv.call_count == len(self.collection_versions)

        # ensure the appropriate pks were used
        call_pks = sorted([str(x.args[0].pk) for x in mock_rebuild_cv.mock_calls])
        expected_pks = sorted([str(x.pk) for x in expected_cvs])
        assert call_pks == expected_pks

    @mock.patch("pulp_ansible.app.tasks.collections._rebuild_collection_version_meta")
    @mock.patch("pulp_ansible.app.tasks.collections.ProgressReport")
    def test_reimport_repository_rebuilds_namespace(self, mock_progress_report, mock_rebuild_cv):
        """Make sure only the namespace CVs in the repo are rebuilt."""
        rebuild_repository_collection_versions_metadata(
            self.repo.latest_version().pk, namespace="foo"
        )

        # ensure the function was called once for each namespace cv
        expected_cvs = [x for x in self.collection_versions if x.namespace == "foo"]
        assert mock_rebuild_cv.call_count == len(expected_cvs)

        # ensure the appropriate pks were used
        call_pks = sorted([str(x.args[0].pk) for x in mock_rebuild_cv.mock_calls])
        expected_pks = sorted([str(x.pk) for x in expected_cvs])
        assert call_pks == expected_pks

    @mock.patch("pulp_ansible.app.tasks.collections._rebuild_collection_version_meta")
    @mock.patch("pulp_ansible.app.tasks.collections.ProgressReport")
    def test_reimport_repository_rebuilds_name(self, mock_progress_report, mock_rebuild_cv):
        """Make sure only the named CVs in the repo are rebuilt."""
        rebuild_repository_collection_versions_metadata(self.repo.latest_version().pk, name="baz")

        # ensure the function was called once for each namespace cv
        expected_cvs = [x for x in self.collection_versions if x.name == "baz"]
        assert mock_rebuild_cv.call_count == len(expected_cvs)

        # ensure the appropriate pks were used
        call_pks = sorted([str(x.args[0].pk) for x in mock_rebuild_cv.mock_calls])
        expected_pks = sorted([str(x.pk) for x in expected_cvs])
        assert call_pks == expected_pks


class TestCollectionVersionHighest(TestCase):
    """Test Collection Re-Import."""

    def test_is_highest_set(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1")
            .first()
            .is_highest
            is True
        )

    def test_is_highest_set_on_multple_stable_releases(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1"),
            (namespace, name, "2.0.1"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="2.0.1")
            .first()
            .is_highest
            is True
        )

    def test_is_highest_set_on_single_prerelease(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1-rc2"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc2")
            .first()
            .is_highest
            is True
        )

    def test_is_highest_set_on_multiple_prereleases(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1-rc1"),
            (namespace, name, "1.0.1-rc2"),
            (namespace, name, "1.0.1-rc3"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc1")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc2")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc3")
            .first()
            .is_highest
            is True
        )

    def test_is_highest_set_on_multiple_prereleases_one_pass(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1-rc1"),
            (namespace, name, "1.0.1-rc2"),
            (namespace, name, "1.0.1-rc3"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        _update_highest_version(collection_versions[1])

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc1")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc2")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc3")
            .first()
            .is_highest
            is True
        )

    def test_is_highest_set_on_multiple_prereleases_backwards_order(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1-rc4"),
            (namespace, name, "1.0.1-rc1"),
            (namespace, name, "1.0.1-rc2"),
            (namespace, name, "1.0.1-rc3"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions[::-1]:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc1")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc2")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc3")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1-rc4")
            .first()
            .is_highest
            is True
        )

    def test_prerelease_not_higher_than_stable(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "1.0.1"),
            (namespace, name, "2.0.0-rc1"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="1.0.1")
            .first()
            .is_highest
            is True
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="2.0.0-rc1")
            .first()
            .is_highest
            is False
        )

    def test_prerelease_matches_stable(self):
        namespace = randstr()
        name = randstr()
        specs = [
            (namespace, name, "2.0.0-rc1"),
            (namespace, name, "2.0.0"),
        ]

        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        for cv in collection_versions:
            _update_highest_version(cv)

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="2.0.0-rc1")
            .first()
            .is_highest
            is False
        )

        assert (
            CollectionVersion.objects.filter(namespace=namespace, name=name, version="2.0.0")
            .first()
            .is_highest
            is True
        )
