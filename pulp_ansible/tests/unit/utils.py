import contextlib
import hashlib
import os
import random
import shutil
import string
import subprocess
import tempfile
import yaml

from django.core.files.uploadedfile import SimpleUploadedFile

from pulp_ansible.app.models import Collection
from pulp_ansible.app.models import CollectionVersion
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.models import ContentArtifact


def randstr():
    return "".join(random.choices(string.ascii_lowercase, k=8))


@contextlib.contextmanager
def make_cv_tarball(namespace, name, version):
    """Create a collection version from scratch."""
    tmpdir = tempfile.mkdtemp()
    subprocess.run(f"ansible-galaxy collection init {namespace}.{name}", shell=True, cwd=tmpdir)
    os.makedirs(os.path.join(tmpdir, namespace, name, "meta"), exist_ok=True)
    with open(os.path.join(tmpdir, namespace, name, "meta", "runtime.yml"), "w") as f:
        f.write('requires_ansible: ">=2.13"\n')
    with open(os.path.join(tmpdir, namespace, name, "README.md"), "w") as f:
        f.write("# title\ncollection docs\n")
    if version is not None:
        with open(os.path.join(tmpdir, namespace, name, "galaxy.yml"), "r") as f:
            gdata = yaml.safe_load(f.read())
        gdata["version"] = version
        with open(os.path.join(tmpdir, namespace, name, "galaxy.yml"), "w") as f:
            f.write(yaml.safe_dump(gdata))
    build_pid = subprocess.run(
        "ansible-galaxy collection build .",
        shell=True,
        cwd=os.path.join(tmpdir, namespace, name),
        stdout=subprocess.PIPE,
        check=True,
    )
    tarfn = build_pid.stdout.decode("utf-8").strip().split()[-1]
    yield tarfn
    shutil.rmtree(tmpdir)


def build_cvs_from_specs(specs):
    """Make CVs from a list of [namespace, name, version] specs."""
    collection_versions = []
    for spec in specs:
        with make_cv_tarball(spec[0], spec[1], spec[2]) as tarfn:
            with open(tarfn, "rb") as fp:
                rawbin = fp.read()
            artifact = Artifact.objects.create(
                size=os.path.getsize(tarfn),
                file=SimpleUploadedFile(tarfn, rawbin),
                **{
                    algorithm: hashlib.new(algorithm, rawbin).hexdigest()
                    for algorithm in Artifact.DIGEST_FIELDS
                },
            )

        col, _ = Collection.objects.get_or_create(name=spec[0])
        cv = CollectionVersion.objects.create(
            collection=col, sha256=artifact.sha256, namespace=spec[0], name=spec[1], version=spec[2]
        )
        collection_versions.append(cv)

        ContentArtifact.objects.create(
            artifact=artifact, content=cv, relative_path=cv.relative_path
        )

    return collection_versions
