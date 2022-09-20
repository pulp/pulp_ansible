import hashlib
import os
import subprocess
import tempfile

from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from pulp_ansible.app.models import AnsibleDistribution
from pulp_ansible.app.models import AnsibleRepository
from pulp_ansible.app.models import Collection
from pulp_ansible.app.models import CollectionVersion
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.models import ContentArtifact

from pulp_ansible.app.tasks.collections import rebuild_collection_version_meta
from pulp_ansible.app.tasks.collections import rebuild_repository_collection_versions_metadata


def make_cv_tarball(namespace, name, version):
    """Create a collection version from scratch."""
    tdir = tempfile.mkdtemp()
    subprocess.run(f"ansible-galaxy collection init {namespace}.{name}", shell=True, cwd=tdir)
    os.makedirs(os.path.join(tdir, namespace, name, "meta"))
    with open(os.path.join(tdir, namespace, name, "meta", "runtime.yml"), "w") as f:
        f.write('requires_ansible: ">=2.13"\n')
    with open(os.path.join(tdir, namespace, name, "README.md"), "w") as f:
        f.write("# title\ncollection docs\n")
    build_pid = subprocess.run(
        "ansible-galaxy collection build .",
        shell=True,
        cwd=os.path.join(tdir, namespace, name),
        stdout=subprocess.PIPE,
    )
    tarfn = build_pid.stdout.decode("utf-8").strip().split()[-1]
    return tarfn


class TestCollectionReImport(TestCase):
    """Test Collection Re-Import."""

    def setUp(self):
        """Make all the test data."""
        self.collection_versions = []

        specs = [
            ("foo", "bar", "1.0.0"),
            ("foo", "baz", "1.0.0"),
            ("zip", "drive", "1.0.0"),
        ]

        for spec in specs:
            tarfn = make_cv_tarball(spec[0], spec[1], None)
            rawbin = open(tarfn, "rb").read()
            artifact = Artifact.objects.create(
                sha224=hashlib.sha224(rawbin).hexdigest(),
                sha256=hashlib.sha256(rawbin).hexdigest(),
                sha384=hashlib.sha384(rawbin).hexdigest(),
                sha512=hashlib.sha512(rawbin).hexdigest(),
                size=os.path.getsize(tarfn),
                file=SimpleUploadedFile(tarfn, rawbin),
            )
            artifact.save()

            col, _ = Collection.objects.get_or_create(name=spec[0])
            col.save()
            cv = CollectionVersion(collection=col, namespace=spec[0], name=spec[1], version=spec[2])
            cv.save()
            ca = ContentArtifact.objects.create(
                artifact=artifact, content=cv, relative_path=cv.relative_path
            )
            ca.save()
            self.collection_versions.append(cv)

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
        rebuild_collection_version_meta(this_cv.pk)
        cv = CollectionVersion.objects.get(pulp_id=this_cv.pk)
        assert cv.docs_blob["collection_readme"]["html"] == "<h1>title</h1>\n<p>collection docs</p>"

    def test_reimport_repository_rebuilds_all_collections(self):
        """Make sure each CV in the repo is rebuilt."""
        fpath = "pulp_ansible.app.tasks.collections.rebuild_collection_version_meta"
        with mock.patch(fpath) as mocked_rebuild_cv:
            rebuild_repository_collection_versions_metadata(self.repo.pulp_id)

            # ensure the function was called once for each cv
            assert mocked_rebuild_cv.call_count == len(self.collection_versions)

            # ensure the appropriate pks were used
            call_pks = [x.args[0] for x in mocked_rebuild_cv.mock_calls]
            call_pks = sorted(call_pks)
            expected_pks = [str(x.pulp_id) for x in self.collection_versions]
            expected_pks = sorted(expected_pks)
            assert call_pks == expected_pks

    def test_reimport_repository_rebuilds_namespace(self):
        """Make sure only the namespace CVs in the repo are rebuilt."""
        fpath = "pulp_ansible.app.tasks.collections.rebuild_collection_version_meta"
        with mock.patch(fpath) as mocked_rebuild_cv:
            rebuild_repository_collection_versions_metadata(self.repo.pulp_id, namespace="foo")

            # ensure the function was called once for each namespace cv
            expected_cvs = [x for x in self.collection_versions if x.namespace == "foo"]
            assert mocked_rebuild_cv.call_count == len(expected_cvs)

            # ensure the appropriate pks were used
            call_pks = [x.args[0] for x in mocked_rebuild_cv.mock_calls]
            call_pks = sorted(call_pks)
            expected_pks = [str(x.pulp_id) for x in expected_cvs]
            expected_pks = sorted(expected_pks)
            assert call_pks == expected_pks

    def test_reimport_repository_rebuilds_name(self):
        """Make sure only the named CVs in the repo are rebuilt."""
        fpath = "pulp_ansible.app.tasks.collections.rebuild_collection_version_meta"
        with mock.patch(fpath) as mocked_rebuild_cv:
            rebuild_repository_collection_versions_metadata(self.repo.pulp_id, name="baz")

            # ensure the function was called once for each namespace cv
            expected_cvs = [x for x in self.collection_versions if x.name == "baz"]
            assert mocked_rebuild_cv.call_count == len(expected_cvs)

            # ensure the appropriate pks were used
            call_pks = [x.args[0] for x in mocked_rebuild_cv.mock_calls]
            call_pks = sorted(call_pks)
            expected_pks = [str(x.pulp_id) for x in expected_cvs]
            expected_pks = sorted(expected_pks)
            assert call_pks == expected_pks
