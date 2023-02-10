import copy
import logging
import shutil
import os
import random
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

from pulpcore.client.pulp_ansible import (
    ApiClient as AnsibleApiClient,
    PulpAnsibleApiV3CollectionsApi,
)


logger = logging.getLogger(__name__)


def keys_from_specs(specs):
    keys = sorted(
        [
            x["repository_name"] + ":" + x["namespace"] + ":" + x["name"] + ":" + x["version"]
            for x in specs
        ]
    )
    return sorted(keys)


def keys_from_results(specs):
    return keys_from_specs(specs)


def compare_keys(a, b):
    result = ""
    all_keys = sorted(set(a + b))
    for ak in all_keys:
        if ak not in a:
            result += f"None < {ak}\n"
        if ak not in b:
            result += f"{ak} > None\n"
    return result


def assemble_collection_version_url(repo_name, namespace, name, version):
    return (
        "/pulp_ansible/galaxy/"
        + repo_name
        + "/api/v3/plugin/ansible/content/"
        + repo_name
        + "/collections/index/"
        + namespace
        + "/"
        + name
        + "/versions/"
        + version
        + "/"
    )


@pytest.fixture(scope="session")
def pulp_client():
    cfg = config.get_config()
    client = api.Client(cfg)
    headers = cfg.custom.get("headers", None)
    if headers:
        client.request_kwargs.setdefault("headers", {}).update(headers)

    client.client_side_validation = False

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


def get_collection_versions_by_repo(pulp_client, repo_names=None):
    """Make a mapping of repositories and their CV content."""
    if repo_names is None:
        repos = get_repositories(pulp_client)
        repo_names = list(repos.keys())

    cvs = {}

    for repo_name in repo_names:
        next_url = (
            "/pulp_ansible/galaxy/"
            + repo_name
            + "/api/v3/plugin/ansible/content/"
            + repo_name
            + "/collections/index/"
        )
        while next_url:
            resp = pulp_client.get(next_url)
            next_url = resp["links"]["next"]
            for collection in resp["data"]:
                next_cv_url = collection["versions_url"]
                while next_cv_url:
                    cvresp = pulp_client.get(next_cv_url)
                    next_cv_url = cvresp["links"]["next"]
                    for cv_summary in cvresp["data"]:
                        cv_info = pulp_client.get(cv_summary["href"])
                        key = (
                            repo_name,
                            cv_info["namespace"]["name"],
                            cv_info["name"],
                            cv_info["version"],
                        )
                        cvs[key] = cv_info

    return cvs


def get_collection_versions(pulp_client):
    cversions = pulp_client.get("/pulp/api/v3/content/ansible/collection_versions/")
    return dict(((x["namespace"], x["name"], x["version"]), x) for x in cversions)


def get_repositories(pulp_client):
    repos = pulp_client.get(ANSIBLE_REPO_PATH)
    repos = dict((x["name"], x) for x in repos)
    return repos


@pytest.mark.pulp_on_localhost
@pytest.fixture()
def search_specs(
    pulp_client,
    tmp_path,
    ansible_repo_api_client,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
):
    # define signing service
    signing_service = ascii_armored_detached_signing_service
    signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}

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
            "signed": True,
        },
        {
            "namespace": "foo",
            "name": "bar",
            "version": "1.0.1",
            "tags": ["a", "b", "c"],
            "has_distribution": False,
            "repository_name": "automation-hub-x",
            "signed": True,
        },
        {
            "namespace": "foo",
            "name": "baz",
            "version": "1.0.1",
            "tags": ["d", "e", "f"],
            "dependencies": {"foo.bar": ">=1.0.0"},
            "repository_name": "automation-hub-2",
            "signed": True,
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.0",
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-1",
            "signed": True,
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.0",
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-3",
            "signed": False,
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.1",
            "dependencies": {"foo.bar": ">=1.0.0"},
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-2",
            "signed": True,
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "12.25.2-rc.1",
            "dependencies": {"foo.bar": ">=1.0.0"},
            "tags": ["trees", "sleighs", "gifts"],
            "repository_name": "automation-hub-2",
            "signed": True,
        },
        {
            "namespace": "jingle",
            "name": "bellz",
            "version": "11.0.1",
            "tags": ["new_but_not_really_new"],
            "repository_name": "automation-hub-2",
            "signed": True,
        },
        {
            "namespace": "pink",
            "name": "panther",
            "version": "1.0.0",
            "tags": [],
            "repository_name": "automation-hub-3",
            "signed": True,
            "removed": True,
        },
        {
            "namespace": "pink",
            "name": "panther",
            "version": "1.0.0",
            "tags": [],
            "repository_name": "automation-hub-2",
            "signed": True,
            "removed": False,
        },
        {
            "namespace": "pink",
            "name": "panther",
            "version": "2.0.0",
            "tags": [],
            "repository_name": "automation-hub-1",
            "signed": True,
            "readded": True,
        },
        {
            "namespace": "i_was",
            "name": "a_bad_idea",
            "version": "1.0.0",
            "tags": [],
            "repository_name": "automation-hub-1",
            "deprecated": True,
        },
    ]

    # "locking" means the system is populated with everything each
    # subtest in the calling class needed so we don't need to clean
    # up or make anything new yet.
    if not os.path.exists("/tmp/search_spec_lock.txt"):
        reponames = sorted(set([x["repository_name"] for x in specs]))

        # cleanup ...
        # for rname in sorted(set(x["repository_name"] for x in specs)):
        for rname in reponames:
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
                repository_href = pulp_repo["pulp_href"]
                res = monitor_task(ansible_repo_api_client.sign(repository_href, signing_body).task)
                assert res.state == "completed"

            # make the distribution
            if spec["repository_name"] not in created_dists:
                dist_data = gen_distribution(
                    name=pulp_repo["name"],
                    base_path=pulp_repo["name"],
                    repository=pulp_repo["pulp_href"],
                )
                pulp_dist = pulp_client.post(ANSIBLE_DISTRIBUTION_PATH, dist_data)
                created_dists[spec["repository_name"]] = pulp_dist

        # keep track of what got uploaded
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

            if spec["repository_name"] in created_dists:
                pulp_dist = created_dists[spec["repository_name"]]
            else:
                pulp_dist = {"base_path": spec["repository_name"]}

            if ckey not in uploaded_artifacts:
                # upload will put it in the repo automatically ...
                UPLOAD_PATH = get_galaxy_url(pulp_dist["base_path"], "/v3/artifacts/collections/")
                # print(f"UPLOAD_PATH: {UPLOAD_PATH}")
                collection = {
                    "file": (os.path.basename(spec["artifact"]), open(spec["artifact"], "rb"))
                }
                response = pulp_client.using_handler(upload_handler).post(
                    UPLOAD_PATH, files=collection
                )
                assert response["state"] != "failed", response["error"]
                uploaded_artifacts[ckey] = new_fn

            else:
                # copy to the repo ...
                # https://docs.pulpproject.org/pulp_rpm/workflows/copy.html
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]
                cvs = get_collection_versions(pulp_client)
                this_cv = cvs[ckey]
                cv_href = this_cv["pulp_href"]
                payload = {"add_content_units": [cv_href]}
                # import epdb; epdb.st()
                # resp = pulp_client.post(repo_href + "modify/", payload)
                pulp_client.post(repo_href + "modify/", payload)
                # import epdb; epdb.st()

            # sign it ...
            if spec.get("signed"):
                cvs = get_collection_versions(pulp_client)
                ckey = (spec["namespace"], spec["name"], spec["version"])
                cv = cvs[ckey]
                collection_url = cv["pulp_href"]
                repo = created_repos[spec["repository_name"]]
                body = {
                    "content_units": [collection_url],
                    "signing_service": ascii_armored_detached_signing_service.pulp_href,
                }
                res = monitor_task(ansible_repo_api_client.sign(repo["pulp_href"], body).task)
                assert res.state == "completed"

        # delete distributions so that some repos can hold CVs but not be "distributed"
        current_dists = pulp_client.get(ANSIBLE_DISTRIBUTION_PATH)
        current_dists = dict((x["name"], x) for x in current_dists)
        distros_deleted = []
        for spec in specs:
            if not spec.get("has_distribution", True):
                dname = spec["repository_name"]
                if dname in distros_deleted:
                    continue
                pulp_client.delete(current_dists[dname]["pulp_href"])
                distros_deleted.append(dname)

        # limit our actions to only the repos under test ...
        reponames = sorted(set([x["repository_name"] for x in specs]))

        # remove stuff -after- it's copied around ...
        for ids, spec in enumerate(specs):
            if spec.get("removed") or spec.get("readded"):
                cvs = get_collection_versions(pulp_client)
                ckey = (spec["namespace"], spec["name"], spec["version"])
                cv = cvs[ckey]
                collection_url = cv["pulp_href"]
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]

                payload = {"remove_content_units": [collection_url]}
                pulp_client.post(repo_href + "modify/", payload)

        # re-add stuff
        for ids, spec in enumerate(specs):
            if spec.get("readded"):
                cvs = get_collection_versions(pulp_client)
                ckey = (spec["namespace"], spec["name"], spec["version"])
                cv = cvs[ckey]
                collection_url = cv["pulp_href"]
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]

                payload = {"add_content_units": [collection_url]}
                pulp_client.post(repo_href + "modify/", payload)

        # generate some new repo version numbers to ensure content shows up
        reponames = [x["repository_name"] for x in specs]
        for reponame in reponames:
            repo = created_repos[spec["repository_name"]]
            repo_href = repo["pulp_href"]

            # what should be IN the repo already?
            candidates = [x for x in specs if x.get("repository_name") == reponame]
            candidates = [x for x in candidates if not x.get("removed") and not x.get("readded")]
            if not candidates:
                continue

            # pick one at random
            spec = random.choice(candidates)
            ckey = (spec["namespace"], spec["name"], spec["version"])
            cv = cvs[ckey]
            collection_url = cv["pulp_href"]

            # add it to the repo to bump the repo version and
            # validate the other CVs continue to live in "latest"
            payload = {"add_content_units": [collection_url]}
            pulp_client.post(repo_href + "modify/", payload)

        # make some deprecations ...
        for ids, spec in enumerate(specs):
            if spec.get("deprecated"):
                cfg = config.get_config()
                configuration = cfg.get_bindings_config()
                this_client = AnsibleApiClient(configuration)
                collections_v3api = PulpAnsibleApiV3CollectionsApi(this_client)
                task = collections_v3api.update(
                    spec["name"], spec["namespace"], spec["repository_name"], {"deprecated": True}
                )
                result = monitor_task(task.task)
                assert result.state == "completed", result

        # set the lock and expect the calling class or function to handle unlocking
        with open("/tmp/search_spec_lock.txt", "w") as f:
            f.write("locked=true")

    # make new specs with the enumerated content of all repos ...
    reponames = sorted(
        set([x["repository_name"] for x in specs if x.get("has_distribution", True)])
    )
    cvbr = get_collection_versions_by_repo(pulp_client, repo_names=reponames)
    new_specs = []
    for k, v in cvbr.items():
        ds = {
            "repository_name": k[0],
            "namespace": k[1],
            "name": k[2],
            "version": k[3],
            "tags": v["metadata"]["tags"],
            "dependencies": v["metadata"]["dependencies"],
            "signed": False,
            "deprecated": False,
        }
        if v["signatures"]:
            ds["signed"] = True
        collection_url = v["collection"]["href"]
        collection = pulp_client.get(collection_url)
        ds["deprecated"] = collection["deprecated"]
        new_specs.append(ds)

    yield new_specs


class TestCrossRepoSearch:
    """Validate the cross repo search endpoint."""

    @classmethod
    def setup_class(cls):
        """Make spec building a singleton."""
        if os.path.exists("/tmp/search_spec_lock.txt"):
            os.remove("/tmp/search_spec_lock.txt")

    @classmethod
    def teardown_class(cls):
        """Make spec building a singleton."""
        if os.path.exists("/tmp/search_spec_lock.txt"):
            os.remove("/tmp/search_spec_lock.txt")

    def get_paginated_results(self, pulp_client, url):
        results = []
        next_page = url
        while next_page:
            resp = pulp_client.get(next_page)
            results.extend(resp["data"])
            next_page = None
            if resp["links"]["next"]:
                next_page = resp["links"]["next"]
        return results

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_all(self, pulp_client, search_specs):
        """Get everything."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # no filters (except for reponames) ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params
        # resp1 = pulp_client.get(search_url)
        resp1 = self.get_paginated_results(pulp_client, search_url)

        skeys = keys_from_specs(search_specs)
        rkeys = keys_from_results(resp1)
        comparison = compare_keys(skeys, rkeys)
        assert len(skeys) == len(rkeys), comparison

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_namespace(self, pulp_client, search_specs):
        """Get only CV's in a specific namespace."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by namespace ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&namespace=foo"
        # resp2 = pulp_client.get(search_url)
        resp2 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if x["namespace"] == "foo"]
        keys = keys_from_specs(keys)
        assert len(resp2) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_name(self, pulp_client, search_specs):
        """Get only CV's with a specific name."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by name ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&name=bellz"
        # resp3 = pulp_client.get(search_url)
        resp3 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if x["name"] == "bellz"]
        keys = keys_from_specs(keys)
        assert len(resp3) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_q(self, pulp_client, search_specs):
        """Get only CV's with that match a keyword by the q param."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by q ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&q=gifts"
        # resp5 = pulp_client.get(search_url)
        resp5 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if x["name"] == "bellz"]
        keys = [x for x in search_specs if "gifts" in x["tags"]]
        keys = keys_from_specs(keys)
        assert len(resp5) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_keywords(self, pulp_client, search_specs):
        """Get only CV's with that match a keyword by the keyword param."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by keywords
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&keywords=gifts"
        # resp6 = pulp_client.get(search_url)
        resp6 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if "gifts" in x["tags"]]
        keys = keys_from_specs(keys)
        assert len(resp6) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_dependency(self, pulp_client, search_specs):
        """Get only CV's with that have a specific dependency."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by dependency ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&dependency=foo.bar"
        # resp7 = pulp_client.get(search_url)
        resp7 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if "foo.bar" in x.get("dependencies", {})]
        keys = keys_from_specs(keys)
        assert len(resp7) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_version(self, pulp_client, search_specs):
        """Get only CV's with that have a specific version."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by version ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&version=1.0.1"
        # resp8 = pulp_client.get(search_url)
        resp8 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if x["version"] == "1.0.1"]
        keys = keys_from_specs(keys)
        assert len(resp8) == len(keys)

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_deprecated(self, pulp_client, search_specs):
        """Get only CV's that are deprecated."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by deprecated True/true/False/false/1/0 ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&deprecated=True"
        # resp9 = pulp_client.get(search_url)
        resp9 = self.get_paginated_results(pulp_client, search_url)
        skeys = keys_from_specs([x for x in search_specs if x.get("deprecated") is True])
        rkeys = keys_from_results(resp9)
        comparison = compare_keys(rkeys, skeys)
        assert len(rkeys) == len(skeys), comparison

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_not_deprecated(self, pulp_client, search_specs):
        """Get only CV's that are not deprecated."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by deprecated True/true/False/false/1/0 ...
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&deprecated=False"
        # resp9 = pulp_client.get(search_url)
        resp9 = self.get_paginated_results(pulp_client, search_url)
        skeys = keys_from_specs([x for x in search_specs if x.get("deprecated", False) is False])
        rkeys = keys_from_results(resp9)
        comparison = compare_keys(rkeys, skeys)
        assert len(rkeys) == len(skeys), comparison

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_signed(self, pulp_client, search_specs):
        """Get only CV's that are signed."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by sign state = True
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&signed=True"
        # resp10 = pulp_client.get(search_url)
        resp10 = self.get_paginated_results(pulp_client, search_url)
        skeys = [x for x in search_specs if x.get("signed") is True]
        skeys = keys_from_specs(skeys)
        rkeys = keys_from_specs(resp10)
        comparison = compare_keys(skeys, rkeys)
        assert len(rkeys) == len(skeys), comparison

    @pytest.mark.pulp_on_localhost
    def test_collection_version_search_by_not_signed(self, pulp_client, search_specs):
        """Get only CV's that are not signed."""

        # we should never see things that were removed from the repos
        search_specs = [x for x in search_specs if not x.get("removed")]

        # limit searches to related repos
        repo_names = sorted(set([x["repository_name"] for x in search_specs]))
        repo_name_params = "repository=" + ",".join(repo_names)

        # by sign state = False
        search_url = (
            "/pulp_ansible/galaxy/default/api/v3/plugin/ansible/search/collection-versions/"
        )
        search_url += "?" + repo_name_params + "&signed=False"
        # resp11 = pulp_client.get(search_url)
        resp11 = self.get_paginated_results(pulp_client, search_url)
        keys = [x for x in search_specs if x.get("signed") is False]
        keys = keys_from_specs(keys)
        assert len(resp11) == len(keys)
