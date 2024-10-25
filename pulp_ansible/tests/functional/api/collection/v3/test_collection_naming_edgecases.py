import hashlib
import json
import subprocess
import os

import pytest

from pulpcore.client.pulp_ansible.exceptions import ApiException
from pulp_ansible.tests.functional.utils import randstr


def busted_collection_build(basedir=None, namespace=None, name=None, version=None):
    """Make artifacts with namespaces and names that wouldn't normally be allowed."""

    def file_checksum(fp):
        with open(fp, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
        return checksum

    # make a content dir
    content_dir = os.path.join(basedir, "content")
    os.makedirs(content_dir)

    # make various files
    for dname in ["docs", "plugins", "roles"]:
        os.makedirs(os.path.join(content_dir, dname))
    with open(os.path.join(content_dir, "README.md"), "w") as f:
        f.write("")
    with open(os.path.join(content_dir, "plugins", "README.md"), "w") as f:
        f.write("")

    # make files.json
    fdata = {"files": [], "format": 1}
    for root, dirs, files in os.walk(content_dir):
        for dirname in dirs:
            dirpath = os.path.join(root, dirname)
            relative_dir = dirpath.replace(content_dir + "/", "")
            fdata["files"].append(
                {
                    "name": relative_dir,
                    "ftype": "dir",
                    "chksum_type": None,
                    "chksum_sha256": None,
                    "format": 1,
                }
            )
        for filen in files:
            filepath = os.path.join(root, filen)
            relative_file = filepath.replace(content_dir + "/", "")
            fdata["files"].append(
                {
                    "name": relative_file,
                    "ftype": "file",
                    "chksum_type": "sha256",
                    "chksum_sha256": file_checksum(filepath),
                    "format": 1,
                }
            )
    with open(os.path.join(content_dir, "FILES.json"), "w") as f:
        f.write(json.dumps(fdata, indent=2))

    # make manifest.json
    mdata = {
        "format": 1,
        "collection_info": {
            "namespace": namespace,
            "name": name,
            "version": version,
            "authors": ["your name <example@domain.com>"],
            "readme": "README.md",
            "tags": [],
            "description": "your collection description",
            "license": ["GPL-2.0-or-later"],
            "license_file": None,
            "dependencies": {},
            "repository": "http://example.com/repository",
            "homepage": "http://example.com",
            "issues": "http://example.com/issue/tracker",
        },
        "file_manifest_file": {
            "name": "FILES.json",
            "ftype": "file",
            "chksum_type": "sha256",
            "chksum_sha256": file_checksum(os.path.join(content_dir, "FILES.json")),
            "format": 1,
        },
    }
    with open(os.path.join(content_dir, "MANIFEST.json"), "w") as f:
        f.write(json.dumps(mdata, indent=2))

    # make the tarball
    cmd = "tar czvf artifact.tar.gz *"
    subprocess.run(cmd, shell=True, cwd=content_dir)
    return os.path.join(content_dir, "artifact.tar.gz")


@pytest.mark.parallel
def test_collection_named_collections(
    ansible_bindings,
    tmp_path,
    ansible_repo,
    ansible_collection_factory,
    ansible_distribution_factory,
    monitor_task,
):
    """A CV with a name of 'collections' could break url parsing."""
    # https://issues.redhat.com/browse/AAH-2158
    pulp_dist = ansible_distribution_factory(ansible_repo)

    spec = {
        "repository": "https://github.com/foo/bar",
        "namespace": randstr(),
        "name": "collections",
        "version": "1.0.0",
    }
    artifact = ansible_collection_factory(config=spec).filename

    body = {"file": artifact}
    body["repository"] = ansible_repo.pulp_href
    response = ansible_bindings.ContentCollectionVersionsApi.create(**body)
    monitor_task(response.task)

    # validate the collection shows up ...
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi.list(
        pulp_dist.base_path
    )
    assert resp.meta.count == 1
    assert resp.data[0].namespace == spec["namespace"]
    assert resp.data[0].name == spec["name"]

    # validate we can get the direct path to the collection ...
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi.read(
        pulp_dist.base_path, namespace=spec["namespace"], name=spec["name"]
    )
    assert resp.namespace == spec["namespace"]
    assert resp.name == spec["name"]


@pytest.mark.parallel
def test_collection_named_with_slashes(
    ansible_bindings,
    tmp_path,
    ansible_repo,
    ansible_distribution_factory,
):
    """A CV with a slash in the name could break url parsing."""
    # https://issues.redhat.com/browse/AAH-2158
    ansible_distribution_factory(ansible_repo)

    spec = {
        "repository": "https://github.com/foo/bar",
        "namespace": "collections/are/fun",
        "name": "index/foo/myname",
        "version": "1.0.0",
    }

    tarball = busted_collection_build(
        basedir=tmp_path,
        namespace=spec["namespace"],
        name=spec["name"],
        version=spec["version"],
    )

    body = {"file": tarball}
    body["repository"] = ansible_repo.pulp_href

    with pytest.raises(ApiException):
        ansible_bindings.ContentCollectionVersionsApi.create(**body)
