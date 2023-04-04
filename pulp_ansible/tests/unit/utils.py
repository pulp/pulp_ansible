import contextlib
import hashlib
import os
import shutil
import subprocess
import tempfile
import yaml

from django.core.files.uploadedfile import SimpleUploadedFile

from pulp_ansible.app.models import Collection
from pulp_ansible.app.models import CollectionVersion
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.models import ContentArtifact


@contextlib.contextmanager
def make_cv_tarball(namespace, name, version):
    """Create a collection version from scratch."""
    tdir = tempfile.mkdtemp()
    subprocess.run(f"ansible-galaxy collection init {namespace}.{name}", shell=True, cwd=tdir)
    os.makedirs(os.path.join(tdir, namespace, name, "meta"))
    with open(os.path.join(tdir, namespace, name, "meta", "runtime.yml"), "w") as f:
        f.write('requires_ansible: ">=2.13"\n')
    with open(os.path.join(tdir, namespace, name, "README.md"), "w") as f:
        f.write("# title\ncollection docs\n")
    if version is not None:
        with open(os.path.join(tdir, namespace, name, "galaxy.yml"), "r") as f:
            gdata = yaml.safe_load(f.read())
        gdata["version"] = version
        with open(os.path.join(tdir, namespace, name, "galaxy.yml"), "w") as f:
            f.write(yaml.safe_dump(gdata))
    build_pid = subprocess.run(
        "ansible-galaxy collection build .",
        shell=True,
        cwd=os.path.join(tdir, namespace, name),
        stdout=subprocess.PIPE,
    )
    tarfn = build_pid.stdout.decode("utf-8").strip().split()[-1]
    yield tarfn
    shutil.rmtree(tdir)


def build_cvs_from_specs(specs, build_artifacts=True):
    """Make CVs from a list of [namespace, name, version] specs."""
    collection_versions = []
    for spec in specs:
        col, _ = Collection.objects.get_or_create(name=spec[0])
        col.save()
        cv = CollectionVersion(collection=col, namespace=spec[0], name=spec[1], version=spec[2])
        cv.save()
        collection_versions.append(cv)

        if build_artifacts:
            with make_cv_tarball(spec[0], spec[1], spec[2]) as tarfn:
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

            ca = ContentArtifact.objects.create(
                artifact=artifact, content=cv, relative_path=cv.relative_path
            )
            ca.save()

    return collection_versions
