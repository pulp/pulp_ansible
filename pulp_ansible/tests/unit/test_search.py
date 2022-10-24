import hashlib
import itertools
import os
import random
import string

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase

from pulp_ansible.app.models import (
    AnsibleDistribution,
    AnsibleRepository,
    Collection,
    CollectionVersion,
    Tag,
)
from pulp_ansible.tests.unit.helpers import make_cv_tarball
from pulpcore.plugin.models import Artifact, ContentArtifact


class TestSearchUtil(TestCase):

    repo = None
    collections = None

    def setUp(self):

        # make a couple repositories to distrbute the collections around
        #   this is also to prepare for future cross-repo searching
        self.repos = {}
        for repo_name in ["published1", "published2"]:
            self.repos[repo_name] = AnsibleRepository(name=repo_name)
            self.repos[repo_name].save()

        # make a distribution for each repo?
        for repo_name, repo in self.repos.items():
            AnsibleDistribution.objects.create(name=repo_name, base_path=repo_name, repository=repo)

        # make some tarballs
        self.collections = {}
        for i in range(0, 2):
            namespace_name = "".join([random.choice(string.ascii_lowercase) for x in range(0, 5)])
            for j in range(0, 3):
                collection_name = "".join(
                    [random.choice(string.ascii_lowercase) for x in range(0, 5)]
                )
                for v in range(1, 3):
                    vstring = f"1.0.{v}"
                    tarfn = make_cv_tarball(namespace_name, collection_name, vstring)
                    self.collections[(namespace_name, collection_name, vstring)] = {
                        "tags": ["tag" + namespace_name + collection_name + vstring],
                        "tar": tarfn,
                    }

        # "import" the collections
        specs = sorted(list(self.collections.keys()))
        for ids, spec in enumerate(specs):
            cdata = self.collections[spec]

            this_repo_name = random.choice(list(self.repos.keys()))
            this_repo = self.repos[this_repo_name]
            self.collections[spec]["repo"] = this_repo
            self.collections[spec]["repo_name"] = this_repo_name

            # make an artifact
            rawbin = open(cdata["tar"], "rb").read()
            artifact = Artifact.objects.create(
                sha224=hashlib.sha224(rawbin).hexdigest(),
                sha256=hashlib.sha256(rawbin).hexdigest(),
                sha384=hashlib.sha384(rawbin).hexdigest(),
                sha512=hashlib.sha512(rawbin).hexdigest(),
                size=os.path.getsize(tarfn),
                file=SimpleUploadedFile(tarfn, rawbin),
            )
            artifact.save()

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
                cv.save()

            # trigger an update and rebuild of the search vector
            #   THIS IS THE ONLY WAY THAT THE SEARCH VECTOR IS CREATED!
            cv.is_highest = False
            cv.save()

            # bind the artifact to the cv
            ca = ContentArtifact.objects.create(
                artifact=artifact, content=cv, relative_path=cv.relative_path
            )
            ca.save()
            self.collections[spec]["ca"] = ca

            # add the cvs to a repository version
            qs = CollectionVersion.objects.filter(pk=cv.pk)
            with this_repo.new_version() as new_version:
                new_version.add_content(qs)

    def tearDown(self):

        # delete the repos
        for repo in self.repos.values():
            repo.delete()

        # delete collectionversions
        for spec, cdata in self.collections.items():
            cdata["ca"].delete()
            cdata["cv"].delete()

            if os.path.exists(cdata["tar"]):
                os.remove(cdata["tar"])

        # delete the collections
        collections = [x["col"] for x in self.collections.values()]
        collections_deleted = []
        for collection in collections:
            if collection.name in collections_deleted:
                continue
            collection.delete()

    def test_search_vector_has_correct_tags(self):

        # flatten a list of all tags
        all_tags = list(itertools.chain(*[x["tags"] for x in self.collections.values()]))

        # fetch the search vector for every CV
        cursor = connection.cursor()
        cursor.execute("select namespace,name,version,search_vector from ansible_collectionversion")
        rows = cursor.fetchall()
        rmap = {}
        for row in rows:
            rmap[(row[0], row[1], row[2])] = row[3]

        for ckey, cdata in self.collections.items():
            search_vector = rmap[ckey]

            # ensure the right tags got in the vector
            good_matches = [x for x in cdata["tags"] if x in search_vector]
            assert sorted(good_matches) == sorted(cdata["tags"])

            # ensure no other tags got in the vector
            bad_tags = [x for x in all_tags if x not in cdata["tags"]]
            bad_matches = [x for x in bad_tags if x in search_vector]
            assert not bad_matches, f"found unrelated tags in {ckey} search vector {search_vector}"
