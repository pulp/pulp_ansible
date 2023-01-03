import itertools
import random
import string

from django.db import connection
from django.test import TestCase

from pulp_ansible.app.models import (
    AnsibleDistribution,
    AnsibleRepository,
    Collection,
    CollectionVersion,
    CollectionVersionSignature,
    Tag,
)


from pprint import pprint
from django.db.models import Exists, OuterRef, Q, Value, F, Func, CharField
from django.db.models import When, Case


class TestSearchUtil2(TestCase):

    distro = None
    repo = None
    collections = None

    def setUp(self):

        # define 12 random collection version specifications
        self.collections = {}
        for i in range(0, 2):
            namespace_name = "".join([random.choice(string.ascii_lowercase) for x in range(0, 5)])
            for j in range(0, 3):
                collection_name = "".join(
                    [random.choice(string.ascii_lowercase) for x in range(0, 5)]
                )
                for v in range(1, 3):

                    if len(list(self.collections.keys())) >= 1:
                        continue

                    vstring = f"1.0.{v}"
                    self.collections[(namespace_name, collection_name, vstring)] = {
                        "tags": ["tag" + namespace_name + collection_name + vstring],
                    }

        # we want to iterate in a sorted order
        specs = sorted(list(self.collections.keys()))

        # "import" the collections
        for ids, spec in enumerate(specs):

            cdata = self.collections[spec]

            # make the collection
            col, _ = Collection.objects.get_or_create(name=spec[0])
            col.save()
            self.collections[spec]["col"] = col

            # make the collection version
            cv = CollectionVersion(collection=col, namespace=spec[0], name=spec[1], version=spec[2])
            cv.save()
            self.collections[spec]["cv"] = cv

            # add tags ...
            #   ansible_collectionversion -> ansible_collectionversion_tags -> ansible_tags
            for tag_name in cdata["tags"]:
                this_tag, _ = Tag.objects.get_or_create(name=tag_name)
                cv.tags.add(this_tag)

            # trigger an update and rebuild of the search vector
            #   THIS IS THE ONLY WAY THAT THE SEARCH VECTOR IS CREATED!
            cv.is_highest = False
            cv.save()

        # add the collections to a distro+repo
        self.repo = AnsibleRepository(name='foo')
        self.repo.save()
        self.distro = AnsibleDistribution(name='foo', base_path='foo', repository=self.repo)
        self.distro.save()
        with self.repo.new_version() as new_version:
            new_version.add_content(CollectionVersion.objects.all())

        # make a bunch of random repos and distros to obfuscate the results ...
        for x in range(0, 10):
            name = collection_name = "".join([random.choice(string.ascii_lowercase) for x in range(0, 5)])
            new_repo = AnsibleRepository(name=name)
            new_repo.save()
            new_distro = AnsibleDistribution(name=name, base_path=name, repository=new_repo)
            new_distro.save()

    def tearDown(self):

        # delete the distro

        # delete the repo

        # delete collectionversions
        for spec, cdata in self.collections.items():
            cdata["cv"].delete()

        # delete the collections
        collections = [x["col"] for x in self.collections.values()]
        collections_deleted = []
        for collection in collections:
            if collection.name in collections_deleted:
                continue
            collection.delete()
            collections_deleted.append(collection.name)

    def test_new_search(self):

        '''
        repos = AnsibleRepository.objects.all()
        cvs = [x.cast() for x in self.repo.content.all()]
        # cvs[0] in [x.cast() for x in self.distro.repository.content.all()]
        distro_content = [str(x.cast().pk) for x in self.distro.repository.content.all()]
        #import epdb; epdb.st()
        '''
        qs = CollectionVersion.objects.all()

        # add a field to indicate if CV in each distro ...
        for distro in AnsibleDistribution.objects.all():
            kwargs = {
                f"in_distro_{distro.name}": Case(
                    When(pulp_id__in=distro.repository.latest_version().content, then=Value("true")),
                    default=Value("false")
                )
            }
            qs = qs.annotate(**kwargs)

        import epdb; epdb.st()
