import itertools
import random
import string

from django.db import connection
from django.test import TestCase

from pulp_ansible.app.models import (
    Collection,
    CollectionVersion,
    Tag,
)


class TestSearchUtil(TestCase):
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

    def tearDown(self):
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

    def test_search_vector_has_correct_tags(self):
        # flatten a list of all tags
        all_tags = list(itertools.chain(*[x["tags"] for x in self.collections.values()]))

        # fetch the search vector for every CV
        cursor = connection.cursor()
        cursor.execute("select namespace,name,version,search_vector from ansible_collectionversion")
        rows = cursor.fetchall()

        # make a map for quicker reference
        rmap = {}
        for row in rows:
            rmap[(row[0], row[1], row[2])] = row[3]

        # check the search vector on each collectionversion ...
        for ckey, cdata in self.collections.items():
            search_vector = rmap[ckey]
            assert search_vector != "", "search vector was not built"

            # ensure the right tags got in the vector
            good_matches = [x for x in cdata["tags"] if x in search_vector]
            assert sorted(good_matches) == sorted(cdata["tags"])

            # ensure no other tags got in the vector
            bad_tags = [x for x in all_tags if x not in cdata["tags"]]
            bad_matches = [x for x in bad_tags if x in search_vector]
            assert not bad_matches, f"found unrelated tags in {ckey} search vector {search_vector}"
