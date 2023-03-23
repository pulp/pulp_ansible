import hashlib
import os
import subprocess
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile

from pulp_ansible.app.models import Collection
from pulp_ansible.app.models import CollectionVersion
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.models import ContentArtifact


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


def build_cvs_from_specs(specs):
    """Make CVs from namespace.name.version specs."""
    collection_versions = []
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
        collection_versions.append(cv)

    return collection_versions
