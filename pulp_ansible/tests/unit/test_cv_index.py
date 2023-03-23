from django.test import TestCase

from orionutils.generator import randstr

from pulp_ansible.app.models import AnsibleDistribution
from pulp_ansible.app.models import AnsibleRepository
from pulp_ansible.app.models import CollectionVersion
from pulp_ansible.app.models import CrossRepositoryCollectionVersionIndex as CVIndex

from .utils import build_cvs_from_specs


class TestCollectionVersionIndex(TestCase):
    """Test Collection Version Cross Repository Index Behavior."""

    def test_cv_index_removes_cvs(self):
        """Ensure when CVs are removed from a repo, the index is also removed."""
        repo_name = randstr()
        base_path = repo_name
        distro_name = repo_name
        ns = randstr()

        # create a repository
        repo = AnsibleRepository(name=repo_name)
        repo.save()

        # create the distro
        AnsibleDistribution.objects.create(name=distro_name, base_path=base_path, repository=repo)

        # add a collection version ...
        specs = [
            (ns, "foo", "1.0.0"),
            (ns, "bar", "1.0.0"),
        ]
        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        cv_pks = [x.pk for x in collection_versions]
        qs = CollectionVersion.objects.filter(pk__in=cv_pks)
        with repo.new_version() as new_version:
            new_version.add_content(qs)

        # ensure CVs were indexed
        assert CVIndex.objects.filter(repository=repo, repository_version=None).count() == 2

        # remove foo
        to_remove = CollectionVersion.objects.filter(namespace=ns, name="foo", version="1.0.0")
        with repo.new_version() as new_version:
            new_version.remove_content(to_remove)

        # ensure only one index is left for bar
        qs = CVIndex.objects.filter(repository=repo, repository_version=None).order_by(
            "collection_version__version"
        )
        assert qs.count() == 1
        assert qs.first().collection_version.namespace == ns
        assert qs.first().collection_version.name == "bar"
        assert qs.first().collection_version.version == "1.0.0"

    def test_cv_index_retains_ids(self):
        """Ensure old indexes are retained instead of deleted and recreated."""
        repo_name = randstr()
        base_path = repo_name
        distro_name = repo_name
        ns = randstr()

        # create a repository
        repo = AnsibleRepository(name=repo_name)
        repo.save()

        # create the distro
        AnsibleDistribution.objects.create(name=distro_name, base_path=base_path, repository=repo)

        # add a collection version ...
        specs = [
            (ns, "bar", "1.0.0"),
        ]
        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        cv_pks = [x.pk for x in collection_versions]
        qs = CollectionVersion.objects.filter(pk__in=cv_pks)
        with repo.new_version() as new_version:
            new_version.add_content(qs)

        # ensure CVs were indexed
        qs = CVIndex.objects.filter(repository=repo, repository_version=None)
        assert qs.count() == 1

        old_ids = [x.id for x in qs]

        # add 1 more collection version ...
        specs = [
            (ns, "bar", "2.0.0"),
        ]
        collection_versions = build_cvs_from_specs(specs, build_artifacts=False)
        cv_pks = [x.pk for x in collection_versions]
        qs = CollectionVersion.objects.filter(pk__in=cv_pks)
        with repo.new_version() as new_version:
            new_version.add_content(qs)

        # get the indexes and their IDs again ...
        qs = CVIndex.objects.filter(repository=repo, repository_version=None).order_by(
            "collection_version__version"
        )
        assert qs.count() == 2

        new_indexes = [x for x in qs]
        new_ids = [x.id for x in qs]

        # the previous IDs should be in the list ...
        for x in old_ids:
            assert x in new_ids

        assert new_indexes[0].is_highest is False
        assert new_indexes[0].collection_version.version == "1.0.0"
        assert new_indexes[1].is_highest is True
        assert new_indexes[1].collection_version.version == "2.0.0"
