import copy
import logging
import shutil
import os
from urllib.parse import urljoin

import pytest

from orionutils.generator import build_collection

from pulp_smash import api, config
from pulp_smash.pulp3.bindings import delete_orphans
from pulp_smash.pulp3.bindings import monitor_task

from pulp_ansible.tests.functional.utils import (
    gen_distribution,
    gen_repo,
)

from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_REPO_PATH,
    # GALAXY_ANSIBLE_BASE_URL,
)


logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def pulp_client():
    cfg = config.get_config()
    client = api.Client(cfg)
    headers = cfg.custom.get("headers", None)
    if headers:
        client.request_kwargs.setdefault("headers", {}).update(headers)
    return client


def upload_handler(client, response):
    response.raise_for_status()
    logger.debug("response status: %s", response.status_code)
    if response.status_code == 204:
        return response
    # import epdb; epdb.st()
    # api._handle_202(client._cfg, response, client.pulp_host)
    if response.request.method == "POST":
        # import epdb; epdb.st()
        task_url = response.json()["task"]
        task = client.get(task_url)
        while task.get("finished_at") is None:
            # print(task['state'])
            task = client.get(task_url)
        # print(task['state'])
        return task
    else:
        return response.json()


def get_galaxy_url(base, path):
    cfg = config.get_config()
    path = path.lstrip("/")
    GALAXY_API_ROOT = cfg.custom.get(
        "galaxy_api_root", "/pulp_ansible/galaxy/%(base_path)s/api/"
    ) % {"base_path": base}
    return urljoin(GALAXY_API_ROOT, path)


# @pytest.mark.pulp_on_localhost
# @pytest.fixture(scope="session")
@pytest.fixture()
def search_specs(
    pulp_client,
    tmp_path,
    ansible_repo_api_client,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
):
    def get_collection_versions():
        cversions = pulp_client.get("/pulp/api/v3/content/ansible/collection_versions/")
        return dict(((x["namespace"], x["name"], x["version"]), x) for x in cversions)


    # define signing service
    signing_service = ascii_armored_detached_signing_service
    signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}

    # delete_orphans()

    # make a place to store artifacts in between runs ...
    # artifact_cache = os.path.join(tmp_path, "artifacts")
    artifact_cache = os.path.join("/tmp", "artifacts")
    if not os.path.exists(artifact_cache):
        os.makedirs(artifact_cache)

    # map out existing distros
    dists = pulp_client.get(ANSIBLE_DISTRIBUTION_PATH)
    dists = dict((x["name"], x) for x in dists)

    # map out existing repos
    repos = pulp_client.get(ANSIBLE_REPO_PATH)
    repos = dict((x["name"], x) for x in repos)

    # /pulp_ansible/galaxy/<path:path>/api/v3/plugin/ansible/search/collection-versions/
    # /pulp/api/v3/content/ansible/collection_versions/
    # cversions = get_collection_versions()

    specs = [
        {
            "namespace": "foo",
            "name": "bar",
            "version": "1.0.1",
            "tags": ["a", "b", "c"],
            "repository_name": "automation-hub-1",
            "signed": True
        },
        {
            "namespace": "foo",
            "name": "baz",
            "version": "1.0.1",
            "tags": ["d", "e", "f"],
            "dependencies": {"foo.bar": ">=1.0.0"},
            "repository_name": "automation-hub-2",
            "signed": True
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.0",
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-1",
            "signed": True
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.0",
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-3",
            "signed": False
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.1",
            "dependencies": {"foo.bar": ">=1.0.0"},
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-2",
            "signed": True
        },
    ]

    # cleanup ...
    for rname in sorted(set(x["repository_name"] for x in specs)):

        # clean the dist
        try:
            # rname = spec["repository_name"]
            if rname in dists:
                pulp_client.delete(dists[rname]["pulp_href"])
        except Exception:
            pass

        # clean the repo
        try:
            # rname = spec["repository_name"]
            if rname in repos:
                pulp_client.delete(repos[rname]["pulp_href"])
        except Exception:
            pass

    # cv's and artifacts should be orphaned if the repos are gone ...
    delete_orphans()

    created_repos = {}
    created_dists = {}

    # create repo & distro ...
    for ids, spec in enumerate(specs):

        # make the repo
        if spec["repository_name"] not in created_repos:
            repo_data = gen_repo(name=spec["repository_name"])
            pulp_repo = pulp_client.post(ANSIBLE_REPO_PATH, repo_data)
            created_repos[spec["repository_name"]] = pulp_repo

            # sign the repo?
            repository_href = pulp_repo['pulp_href']
            res = monitor_task(ansible_repo_api_client.sign(repository_href, signing_body).task)
            assert res.state == 'completed'

        # make the distribution
        if spec["repository_name"] not in created_dists:
            dist_data = gen_distribution(
                name=pulp_repo["name"],
                base_path=pulp_repo["name"],
                repository=pulp_repo["pulp_href"],
            )
            pulp_dist = pulp_client.post(ANSIBLE_DISTRIBUTION_PATH, dist_data)
            created_dists[spec["repository_name"]] = pulp_dist

    uploaded_artifacts = {}

    # make and upload each cv
    for ids, spec in enumerate(specs):

        ckey = (spec["namespace"], spec["name"], spec["version"])
        spec2 = copy.deepcopy(spec)
        spec2["repository"] = "https://github.com/foo/bar"
        artifact = build_collection(base="skeleton", config=spec2)
        new_fn = os.path.join(artifact_cache, os.path.basename(artifact.filename))
        shutil.copy(artifact.filename, new_fn)
        specs[ids]["artifact"] = new_fn

        pulp_dist = created_dists[spec["repository_name"]]

        if ckey not in uploaded_artifacts:
            # upload will put it in the repo automatically ...

            UPLOAD_PATH = get_galaxy_url(pulp_dist["base_path"], "/v3/artifacts/collections/")
            print(f"UPLOAD_PATH: {UPLOAD_PATH}")
            collection = {
                "file": (os.path.basename(spec["artifact"]), open(spec["artifact"], "rb"))
            }
            response = pulp_client.using_handler(upload_handler).post(UPLOAD_PATH, files=collection)
            assert response["state"] != "failed", response["error"]
            uploaded_artifacts[ckey] = new_fn

        else:
            # copy to the repo ...
            # https://docs.pulpproject.org/pulp_rpm/workflows/copy.html
            print("Artifact already uploaded, need to copy into repo")
            repo = created_repos[spec["repository_name"]]
            repo_href = repo["pulp_href"]
            cvs = get_collection_versions()
            this_cv = cvs[ckey]
            cv_href = this_cv["pulp_href"]
            payload = {"add_content_units": [cv_href]}
            # resp = pulp_client.post(repo_href + "modify/", payload)
            pulp_client.post(repo_href + "modify/", payload)
            # import epdb; epdb.st()

        # sign it ...
        if spec['signed']:
            cvs = get_collection_versions()
            ckey = (spec['namespace'], spec['name'], spec['version'])
            cv = cvs[ckey]
            collection_url = cv['pulp_href']
            repo = created_repos[spec['repository_name']]
            body = {
                "content_units": [collection_url],
                "signing_service": ascii_armored_detached_signing_service.pulp_href
            }
            res = monitor_task(ansible_repo_api_client.sign(repo['pulp_href'], body).task)
            assert res.state == 'completed'

    yield specs


@pytest.mark.pulp_on_localhost
def test_collection_version_search(pulp_client, search_specs):

    def keys_from_specs(specs):
        keys = sorted([
            x['repository_name'] + ':' + x["namespace"] + ":" + x["name"] + ":" + x["version"]
            for x in specs
        ])
        return keys

    # no filters ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    resp1 = pulp_client.get(search_url)
    assert len(resp1) == len(keys_from_specs(search_specs))

    # by namespace ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?namespace=foo"
    resp2 = pulp_client.get(search_url)
    keys = [x for x in search_specs if x["namespace"] == "foo"]
    keys = keys_from_specs(keys)
    assert len(resp2) == len(keys)

    # by name ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?name=bellz"
    resp3 = pulp_client.get(search_url)
    keys = [x for x in search_specs if x["name"] == "bellz"]
    keys = keys_from_specs(keys)
    assert len(resp3) == len(keys)

    # by repository ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?repository=automation-hub-3"
    resp4 = pulp_client.get(search_url)
    keys = [x for x in search_specs if x["repository_name"] == "automation-hub-3"]
    keys = keys_from_specs(keys)
    assert len(resp4) == len(keys)

    # by q ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?q=gifts"
    resp5 = pulp_client.get(search_url)
    keys = [x for x in search_specs if "gifts" in x["tags"]]
    keys = keys_from_specs(keys)
    assert len(resp5) == len(keys)

    # by keywords
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?keywords=gifts"
    resp6 = pulp_client.get(search_url)
    keys = [x for x in search_specs if "gifts" in x["tags"]]
    keys = keys_from_specs(keys)
    assert len(resp6) == len(keys)

    # by dependency ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?dependency=foo.bar"
    resp7 = pulp_client.get(search_url)
    keys = [x for x in search_specs if "foo.bar" in x.get("dependencies", {})]
    keys = keys_from_specs(keys)
    assert len(resp7) == len(keys)

    # by version ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?version=1.0.1"
    resp8 = pulp_client.get(search_url)
    keys = [x for x in search_specs if x["version"] == "1.0.1"]
    keys = keys_from_specs(keys)
    assert len(resp8) == len(keys)

    # by sign state
    # TBD

    # by deprecated True/true/False/false/1/0 ...
    search_url = "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
    search_url += "?deprecated=True"
    resp9 = pulp_client.get(search_url)
    keys = [x for x in search_specs if x.get("deprecated") == True]
    keys = keys_from_specs(keys)
    assert len(resp9) == len(keys)

