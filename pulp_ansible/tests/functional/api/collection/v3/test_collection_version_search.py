import copy
import pickle
import logging
import shutil
import os
import random
import uuid
from semantic_version import Version

import pytest

from orionutils.generator import build_collection
from orionutils.generator import randstr

from pulp_smash.pulp3.bindings import delete_orphans
from pulp_ansible.tests.functional.utils import (
    gen_distribution,
    gen_remote,
    gen_repo,
)


logger = logging.getLogger(__name__)


REPO_SPECS = {
    "automation-hub-1": {
        "pulp_labels": {"special": "True", "galaxy_type": "published_distribution"}
    },
    "automation-hub-2": {"pulp_labels": {"galaxy_type": "sync_repo"}},
}


SPECS = [
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


def is_new_higher(new, old):
    if old.prerelease and not new.prerelease:
        return True
    if not old.prerelease and new.prerelease:
        return False
    return new > old


def keys_from_specs(specs):
    keys = []
    for spec in specs:
        if spec["distribution_repository_version"]:
            key = ":".join(
                [
                    # spec["distribution_name"],
                    "null",
                    spec["repository_name"],
                    str(spec["repository_version_number"]),
                    spec["namespace"]["name"],
                    spec["name"],
                    spec["version"],
                ]
            )
        else:
            key = ":".join(
                [
                    # spec["distribution_name"],
                    "null",
                    spec["repository_name"],
                    # "null",
                    str(spec["repository_version_number"]),
                    spec["namespace"]["name"],
                    spec["name"],
                    spec["version"],
                ]
            )
        keys.append(key)

    return sorted(keys)


def keys_from_client_results(results):
    keys = []
    for cv in results:
        if cv.repository_version:
            key = ":".join(
                [
                    "null",
                    cv.repository.name,
                    str(cv.repository_version),
                    cv.collection_version.namespace,
                    cv.collection_version.name,
                    cv.collection_version.version,
                ]
            )
        else:
            key = ":".join(
                [
                    "null",
                    cv.repository.name,
                    str(cv.repository_version),
                    cv.collection_version.namespace,
                    cv.collection_version.name,
                    cv.collection_version.version,
                ]
            )

        keys.append(key)

    return sorted(keys)


def keys_from_results(specs):
    return keys_from_client_results(specs)


def compare_keys(a, b):
    result = ""
    a_missing = []
    b_missing = []
    all_keys = sorted(set(a + b))
    for ak in all_keys:
        if ak not in a:
            result += f"None < {ak}\n"
            a_missing.append(ak)
        if ak not in b:
            result += f"{ak} > None\n"
            b_missing.append(ak)

    result += "\n"
    result += f"left side missing {len(a_missing)}: {a_missing}\n"
    for x in a_missing:
        result += "\t" + x + "\n"
    result += f"right side missing {len(b_missing)}\n"
    for x in b_missing:
        result += "\t" + x + "\n"

    return result


def get_collection_versions_by_repo(
    ansible_collection_deprecations_api_client,
    ansible_collection_signatures_client,
    ansible_collection_version_api_client,
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    galaxy_v3_content_collections_index_api_client,
    galaxy_v3_content_collections_index_versions_api_client,
    repo_names=None,
):
    """Make a mapping of repositories and their CV content."""

    repos = client_results_to_dict(ansible_repo_api_client.list(limit=1000).results)
    dists = client_results_to_dict(ansible_distro_api_client.list(limit=1000).results)

    repository_dist_map = {}
    repository_version_dist_map = {}
    for dist, dist_info in dists.items():
        if dist_info["repository"]:
            repository_dist_map[dist_info["repository"]] = dist_info
        elif dist_info["repository_version"]:
            repository_version_dist_map[dist_info["repository_version"]] = dist_info

    if repo_names is None:
        repo_names = list(repos.keys())

    cvs = []

    # iterate repos
    for repo_name in repo_names:
        repo_info = repos[repo_name]
        repo_pulp_href = repos[repo_name]["pulp_href"]
        repo_id = repos[repo_name]["pulp_href"].split("/")[-2]
        repo_latest_version = int(repo_info["latest_version_href"].split("/")[-2])
        repository_versions = ansible_repo_version_api_client.list(
            repo_info["pulp_href"], limit=1000
        )

        # iterate repo versions
        for repository_version in repository_versions.results:
            # how is this repo version distributed?
            dist = None
            if repository_version.pulp_href in repository_version_dist_map:
                dist = repository_version_dist_map[repository_version.pulp_href]
            elif (
                repo_pulp_href in repository_dist_map
                and repository_version.number == repo_latest_version
            ):
                dist = repository_dist_map[repo_pulp_href]

            # skip if not distributed
            if dist is None:
                continue

            # shortcut
            present = repository_version.content_summary.present

            # skip if no CVs in the version ...
            if "ansible.collection_version" not in present:
                continue
            if present["ansible.collection_version"]["count"] == 0:
                continue

            # get the deprecations ...
            rv_deprecations = {}
            if (
                "ansible.collection_deprecation" in present
                and present["ansible.collection_deprecation"]["count"] > 0
            ):
                rv_deprecations = ansible_collection_deprecations_api_client.list(
                    repository_version=repository_version.pulp_href, limit=1000
                )
                rv_deprecations = dict(
                    ((x.namespace, x.name), True) for x in rv_deprecations.results
                )

            # get the signatures ...
            rv_signatures = {}
            if (
                "ansible.collection_signature" in present
                and present["ansible.collection_signature"]["count"] > 0
            ):
                rv_signatures = ansible_collection_signatures_client.list(
                    repository_version=repository_version.pulp_href, limit=1000
                )
                rv_signatures = dict(
                    (x.signed_collection.split("/")[-2], x.to_dict()) for x in rv_signatures.results
                )

            # get the collection versions ...
            rv_cvs = ansible_collection_version_api_client.list(
                repository_version=repository_version.pulp_href, limit=1000
            )

            cols = {}
            rv_cvs_info = []
            for cv in rv_cvs.results:
                fqn = (cv.namespace, cv.name)
                if fqn not in cols:
                    cols[fqn] = cv.version
                if is_new_higher(Version(cv.version), Version(cols[fqn])):
                    cols[fqn] = cv.version

                cv_id = cv.pulp_href.split("/")[-2]
                cv_info = {
                    "base_path": dist["base_path"],
                    "distribution_id": dist["pulp_href"].split("/")[-2],
                    "distribution_name": dist["name"],
                    "distribution_repository": dist["repository"],
                    "distribution_repository_version": dist["repository_version"],
                    "repository_name": repo_name,
                    "repository_href": repo_info["pulp_href"],
                    "repository_id": repo_id,
                    "repository_version_number": repository_version.number,
                    "repository_version_is_latest": repository_version.number
                    == repo_latest_version,
                    "namespace": {
                        "name": cv.namespace,
                    },
                    "name": cv.name,
                    "version": cv.version,
                    "highest_version": None,
                    "highest": False,
                    "deprecated": fqn in rv_deprecations,
                    "collection": {
                        "namespace": cv.namespace,
                        "name": cv.name,
                        "deprecated": fqn in rv_deprecations,
                        "highest_version": {
                            "version": None,
                        },
                    },
                    "signatures": [],
                    "tags": [],
                    "dependencies": cv.dependencies,
                    "pulp_labels": repo_info.get("pulp_labels", {}),
                }
                if cv.tags:
                    cv_info["tags"] = [x.name for x in cv.tags]
                if rv_signatures:
                    for signature_cvid, signature_data in rv_signatures.items():
                        if signature_cvid == cv_id:
                            cv_info["signatures"].append(signature_data["pubkey_fingerprint"])
                cv_info["signed"] = len(cv_info["signatures"]) > 0
                rv_cvs_info.append(cv_info)

            # make a second pass to set the highest version for each collection
            for idx, x in enumerate(rv_cvs_info):
                fqn = (x["namespace"]["name"], x["name"])
                if cols[fqn] == x["version"]:
                    rv_cvs_info[idx]["highest"] = True
                rv_cvs_info[idx]["collection"]["highest_version"]["version"] = cols[fqn]
                rv_cvs_info[idx]["highest_version"] = cols[fqn]

            cvs.extend(rv_cvs_info)

    return cvs


def get_collection_versions(ansible_collection_version_api_client):
    cversions = ansible_collection_version_api_client.list(limit=1000)
    return dict(((x.namespace, x.name, x.version), x.to_dict()) for x in cversions.results)


def get_repositories(xclient):
    repos = {}
    for repo in xclient.list().results:
        repos[repo.name] = repo.to_dict()
    return repos


def get_distributions(xclient):
    dists = {}
    for dist in xclient.list().results:
        dists[dist.name] = dist.to_dict()
    return dists


def client_results_to_dict(results):
    rmap = {}
    for result in results:
        rmap[result.name] = result.to_dict()
    return rmap


def delete_repos_and_distros(ansible_distro_api_client, ansible_repo_api_client, reponames=None):
    # map out existing distros
    dists = client_results_to_dict(ansible_distro_api_client.list(limit=1000).results)

    # map out existing repos
    repos = client_results_to_dict(ansible_repo_api_client.list(limit=1000).results)

    # cleanup ...
    # for rname in sorted(set(x["repository_name"] for x in specs)):
    for rname in reponames:
        # clean the dist
        if rname in dists:
            ansible_distro_api_client.delete(dists[rname]["pulp_href"])

        # clean the repo
        if rname in repos:
            ansible_repo_api_client.delete(repos[rname]["pulp_href"])

    # cv's and artifacts should be orphaned if the repos are gone ...
    delete_orphans()


def create_repos_and_dists(
    ansible_distro_api_client,
    ansible_repo_api_client,
    gen_object_with_cleanup,
    monitor_task,
    signing_body,
    repo_specs,
    specs,
):
    created_repos = {}
    created_dists = {}

    # create repo & distro ...
    for ids, spec in enumerate(specs):
        # make the repo
        if spec["repository_name"] not in created_repos:
            repo_data = gen_repo(name=spec["repository_name"])
            if repo_specs.get(spec["repository_name"], {}).get("pulp_labels"):
                repo_data["pulp_labels"] = repo_specs[spec["repository_name"]]["pulp_labels"]

            # pulp_repo = ansible_repo_api_client.create(repo_data)
            pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, repo_data)
            created_repos[pulp_repo.name] = pulp_repo.to_dict()

            # sign the repo?
            repository_href = pulp_repo.pulp_href
            res = monitor_task(ansible_repo_api_client.sign(repository_href, signing_body).task)
            assert res.state == "completed"

        # make the distribution
        if spec["repository_name"] not in created_dists:
            dist_data = gen_distribution(
                name=pulp_repo.name,
                base_path=pulp_repo.name,
                repository=pulp_repo.pulp_href,
            )
            # res = monitor_task(ansible_distro_api_client.create(dist_data).task)
            # dist = ansible_distro_api_client.read(res.created_resources[0])
            dist = gen_object_with_cleanup(ansible_distro_api_client, dist_data)
            created_dists[dist.name] = dist.to_dict()

    return created_dists, created_repos


@pytest.fixture()
def search_specs(
    tmp_path,
    galaxy_v3_collections_api_client,
    ansible_collection_deprecations_api_client,
    ansible_collection_signatures_client,
    ansible_collection_version_api_client,
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    galaxy_v3_content_collections_index_api_client,
    galaxy_v3_content_collections_index_versions_api_client,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
    monitor_task,
    gen_object_with_cleanup,
):
    repo_specs = copy.deepcopy(REPO_SPECS)
    specs = copy.deepcopy(SPECS)
    new_specs = None

    cachefile = os.path.join("/tmp", "xrepo_cache.pickle")

    # if os.path.exists(cachefile):
    #    os.remove(cachefile)

    if not os.path.exists(cachefile):
        # define signing service
        signing_service = ascii_armored_detached_signing_service
        signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}

        # make a place to store artifacts in between runs ...
        # artifact_cache = os.path.join(tmp_path, "artifacts")
        artifact_cache = os.path.join("/tmp", "artifacts")
        if not os.path.exists(artifact_cache):
            os.makedirs(artifact_cache)

        reponames = sorted(set([x["repository_name"] for x in specs]))

        delete_repos_and_distros(
            ansible_distro_api_client, ansible_repo_api_client, reponames=reponames
        )

        created_dists, created_repos = create_repos_and_dists(
            ansible_distro_api_client,
            ansible_repo_api_client,
            gen_object_with_cleanup,
            monitor_task,
            signing_body,
            repo_specs,
            specs,
        )

        # keep track of what got uploaded
        uploaded_artifacts = {}

        # make and upload each cv
        for ids, spec in enumerate(specs):
            ckey = (spec["namespace"], spec["name"], spec["version"])

            """
            if spec["repository_name"] in created_dists:
                pulp_dist = created_dists[spec["repository_name"]]
            else:
                pulp_dist = {"base_path": spec["repository_name"]}
            """

            if ckey not in uploaded_artifacts:
                # upload to the repo ...
                build_spec = copy.deepcopy(spec)
                build_spec["repository"] = "https://github.com/foo/bar"
                artifact = build_collection(base="skeleton", config=build_spec)
                new_fn = os.path.join(artifact_cache, os.path.basename(artifact.filename))
                shutil.move(artifact.filename, new_fn)
                specs[ids]["artifact"] = new_fn
                body = {
                    "file": new_fn,
                    "repository": created_repos[spec["repository_name"]]["pulp_href"],
                }
                res = monitor_task(ansible_collection_version_api_client.create(**body).task)
                assert res.state == "completed"
                uploaded_artifacts[ckey] = new_fn

            else:
                # copy to the repo ...
                # https://docs.pulpproject.org/pulp_rpm/workflows/copy.html
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]
                cvs = get_collection_versions(ansible_collection_version_api_client)
                this_cv = cvs[ckey]
                cv_href = this_cv["pulp_href"]
                payload = {"add_content_units": [cv_href]}
                res = monitor_task(ansible_repo_api_client.modify(repo_href, payload).task)
                assert res.state == "completed"

            # sign it ...
            if spec.get("signed"):
                cvs = get_collection_versions(ansible_collection_version_api_client)
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
        current_dists = ansible_distro_api_client.list().results
        current_dists = dict((x.name, x) for x in current_dists)
        distros_deleted = []
        for spec in specs:
            if not spec.get("has_distribution", True):
                dname = spec["repository_name"]
                if dname in distros_deleted:
                    continue
                ansible_distro_api_client.delete(current_dists[dname].pulp_href)
                distros_deleted.append(dname)

        # limit our actions to only the repos under test ...
        reponames = sorted(set([x["repository_name"] for x in specs]))

        # remove stuff -after- it's copied around ...
        for ids, spec in enumerate(specs):
            if spec.get("removed") or spec.get("readded"):
                cvs = get_collection_versions(ansible_collection_version_api_client)
                ckey = (spec["namespace"], spec["name"], spec["version"])
                cv = cvs[ckey]
                collection_url = cv["pulp_href"]
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]

                payload = {"remove_content_units": [collection_url]}
                res = monitor_task(ansible_repo_api_client.modify(repo_href, payload).task)
                assert res.state == "completed"

        # re-add stuff
        for ids, spec in enumerate(specs):
            if spec.get("readded"):
                cvs = get_collection_versions(ansible_collection_version_api_client)
                ckey = (spec["namespace"], spec["name"], spec["version"])
                cv = cvs[ckey]
                collection_url = cv["pulp_href"]
                repo = created_repos[spec["repository_name"]]
                repo_href = repo["pulp_href"]

                payload = {"add_content_units": [collection_url]}
                res = monitor_task(ansible_repo_api_client.modify(repo_href, payload).task)
                assert res.state == "completed"

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
            res = monitor_task(ansible_repo_api_client.modify(repo_href, payload).task)
            assert res.state == "completed"

        # make some deprecations ...
        for ids, spec in enumerate(specs):
            if spec.get("deprecated"):
                result = monitor_task(
                    galaxy_v3_collections_api_client.update(
                        spec["name"],
                        spec["namespace"],
                        spec["repository_name"],
                        {"deprecated": True},
                    ).task
                )
                assert result.state == "completed", result

        # make new specs with the enumerated content of all repos ...
        reponames = sorted(
            set([x["repository_name"] for x in specs if x.get("has_distribution", True)])
        )

        # map out all of the known distributed CVs
        new_specs = get_collection_versions_by_repo(
            ansible_collection_deprecations_api_client,
            ansible_collection_signatures_client,
            ansible_collection_version_api_client,
            ansible_distro_api_client,
            ansible_repo_api_client,
            ansible_repo_version_api_client,
            galaxy_v3_content_collections_index_api_client,
            galaxy_v3_content_collections_index_versions_api_client,
            repo_names=reponames,
        )

        with open(cachefile, "wb") as f:
            pickle.dump(new_specs, f)

    if new_specs is None:
        with open(cachefile, "rb") as f:
            new_specs = pickle.loads(f.read())

    yield new_specs


class TestCrossRepoSearchFilters:
    """Validate the cross repo search endpoint filters."""

    cachefile = os.path.join("/tmp", "xrepo_cache.pickle")
    clean = True
    # clean = False

    @classmethod
    def setup_class(cls):
        """Make spec building a singleton."""
        if os.path.exists(cls.cachefile):
            os.remove(cls.cachefile)

    @classmethod
    def teardown_class(cls):
        """Make spec building a singleton."""
        if os.path.exists(cls.cachefile):
            os.remove(cls.cachefile)

    def _run_search(self, search_client, specs, specs_filter, search_filters):
        if specs_filter:
            keep = []
            for sfilter in specs_filter:
                for spec in specs:
                    try:
                        if not eval(sfilter):
                            continue
                    except Exception:
                        continue
                    keep.append(spec)
            specs = keep[:]

        skeys = keys_from_specs(specs)

        if "limit" not in search_filters:
            search_filters["limit"] = 1000

        if (
            "repository_name" not in search_filters
            and "repository" not in search_filters
            and "distribution" not in search_filters
            and "distribution_base_path" not in search_filters
        ):
            repo_names = sorted(set([x["repository_name"] for x in specs]))
            search_filters["repository_name"] = repo_names

        if "repository_version" not in search_filters:
            search_filters["repository_version"] = "latest"

        resp = search_client.list(**search_filters)
        rkeys = keys_from_client_results(resp.data)

        comparison = compare_keys(skeys, rkeys)

        assert len(skeys) == len(rkeys), comparison

    def test_collection_version_search_all(self, galaxy_v3_default_search_api_client, search_specs):
        """Get everything."""
        self._run_search(galaxy_v3_default_search_api_client, search_specs, [], {})

    def test_collection_version_search_by_pulp_label(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Filter by the existence of a label on the repo"""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["'special' in spec['pulp_labels']"],
            {"repository_label": "special"},
        )

    def test_collection_version_search_by_pulp_label_value(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Filter by the value of a label on a repo."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec['pulp_labels']['galaxy_type'] == 'sync_repo'"],
            {"repository_label": "galaxy_type=sync_repo"},
        )

    def test_collection_version_search_by_repoid(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get everything (but with repoids)."""
        # reduce to just 2 repos
        repo_ids = sorted(set([x["repository_id"] for x in search_specs]))
        repo_ids = repo_ids[:2]
        repo_ids_str = ",".join(["'" + x + "'" for x in repo_ids])

        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            [f"spec['repository_id'] in [{repo_ids_str}]"],
            {"repository": repo_ids},
        )

    def test_collection_version_search_by_base_path(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get everything (by distribution base path)."""
        base_paths = sorted(set([x["base_path"] for x in search_specs if x.get("base_path")]))
        base_paths = base_paths[:2]
        base_paths_str = ",".join(["'" + x + "'" for x in base_paths])

        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            [f"spec['base_path'] in [{base_paths_str}]"],
            {"distribution_base_path": base_paths},
        )

    def test_collection_version_search_by_distid(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get everything (but with distids)."""
        dist_ids = sorted(set([x["distribution_id"] for x in search_specs]))
        dist_ids = dist_ids[:2]
        dist_ids_str = ",".join(["'" + x + "'" for x in dist_ids])

        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            [f"spec['distribution_id'] in [{dist_ids_str}]"],
            {"distribution": dist_ids},
        )

    def test_collection_version_search_by_namespace(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's in a specific namespace."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec['namespace']['name'] == 'foo'"],
            {"namespace": "foo"},
        )

    def test_collection_version_search_by_name(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's with a specific name."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec['name'] == 'bellz'"],
            {"name": "bellz"},
        )

    # @pytest.mark.skip(reason="pulp_ansible includes pre-releases in is_highest")
    def test_collection_version_search_by_highest(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's that are the highest version."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec.get('highest') is True or spec.get('is_highest') is True"],
            {"highest": True},
        )

    def test_collection_version_search_by_q(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's with that match a keyword by the q param."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["'gifts' in spec['tags']"],
            {"q": "gifts"},
        )

    def test_collection_version_search_by_keywords(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's with that match a keyword by the keyword param."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["'gifts' in spec['tags']"],
            {"keywords": "gifts"},
        )

    def test_collection_version_search_by_dependency(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's with that have a specific dependency."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["'foo.bar' in spec['dependencies']"],
            {"dependency": "foo.bar"},
        )

    def test_collection_version_search_by_version(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's with that have a specific version."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec['version'] == '1.0.1'"],
            {"version": "1.0.1"},
        )

    def test_collection_version_search_by_deprecated(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's that are deprecated."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec['deprecated'] == True"],
            {"deprecated": True},
        )

    def test_collection_version_search_by_not_deprecated(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's that are not deprecated."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["not spec.get('deprecated')"],
            {"deprecated": False},
        )

    def test_collection_version_search_by_signed(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's that are signed."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["spec.get('signed') is True"],
            {"signed": True},
        )

    def test_collection_version_search_by_not_signed(
        self, galaxy_v3_default_search_api_client, search_specs
    ):
        """Get only CV's that are not signed."""
        self._run_search(
            galaxy_v3_default_search_api_client,
            search_specs,
            ["not spec.get('signed')"],
            {"signed": False},
        )


def test_cross_repo_search_index_on_distribution_without_repository(
    ansible_distro_api_client,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure no indexes are created for a repo-less distribution."""
    distro_data = gen_distribution()
    distro = gen_object_with_cleanup(ansible_distro_api_client, distro_data)
    dist_id = distro.pulp_href.split("/")[-2]
    resp = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_distribution_with_repository_latest_version(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure indexes are created for a distribution that points at a repo version."""

    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    build_and_upload_collection(ansible_repo=pulp_repo)

    # get the latest repo version ...
    repository_versions = ansible_repo_version_api_client.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    distro = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository_version": repository_version_latest.pulp_href,
        },
    )

    # make sure the CV was indexed
    dist_id = distro.pulp_href.split("/")[-2]
    resp = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_distribution_with_repository_previous_version(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure indexes are created for a distribution that points at the latest repo version."""

    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    build_and_upload_collection(ansible_repo=pulp_repo)

    # get the latest repo version ...
    repository_versions = ansible_repo_version_api_client.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    distro = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository_version": repository_version_latest.pulp_href,
        },
    )

    # make sure the CV was indexed
    dist_id = distro.pulp_href.split("/")[-2]
    resp = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_repository_without_distribution(
    ansible_repo_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure no indexes are created for a repo without a distribution."""

    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    build_and_upload_collection(ansible_repo=pulp_repo)

    # make sure nothing was indexed
    repo_id = pulp_repo.pulp_href.split("/")[-2]
    resp = galaxy_v3_default_search_api_client.list(limit=1000, repository=[repo_id])
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_repository_version_latest_filter(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure 'latest' is acceptable as a repo version filter string."""
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    build_and_upload_collection(ansible_repo=pulp_repo)

    # get the latest repo version ...
    repository_versions = ansible_repo_version_api_client.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository_version": repository_version_latest.pulp_href,
        },
    )

    # make sure the CV was indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_multi_distro_single_repo(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure indexes are created for a repo with multiple distributions."""

    build_config = {
        "namespace": randstr(),
        "name": randstr(),
        "version": "1.0.1",
    }

    # make the repo
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    repo_id = pulp_repo.pulp_href.split("/")[-2]

    # add a collection to bump the version number
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # get the latest repo version ...
    repository_versions = ansible_repo_version_api_client.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points at the first version
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "_v1",
            "base_path": pulp_repo.name + "_v1",
            "repository_version": repository_version_latest.pulp_href,
        },
    )

    # we should now have 1 index
    # repov1 + cv1

    resp = galaxy_v3_default_search_api_client.list(limit=1000, repository=[repo_id])
    assert resp.meta.count == 1
    assert resp.data[0].repository_version == "1"

    # add a collection to bump the version number
    build_config["version"] = "1.0.2"
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # get the latest repo version ...
    repository_versions = ansible_repo_version_api_client.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points at the second version
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "_v2",
            "base_path": pulp_repo.name + "_v2",
            "repository_version": repository_version_latest.pulp_href,
        },
    )

    # per david, we should have 3 entries now
    # repov1+cv1
    # repov2+cv1
    # repov2+cv2

    resp = galaxy_v3_default_search_api_client.list(limit=1000, repository=[repo_id])
    assert resp.meta.count == 3
    repo_versions = sorted([int(x.repository_version) for x in resp.data])
    assert repo_versions == [1, 2, 2]

    # add a collection to bump the version number
    build_config["version"] = "1.0.3"
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # make a distro that points at the repository instead of a version
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "_vN",
            "base_path": pulp_repo.name + "_vN",
            "repository": pulp_repo.pulp_href,
        },
    )

    # per david, we should have 6 entries now
    # repov=1 + cv1
    # repov=2 + cv1,cv2
    # repov=null + cv1,cv2,cv3

    resp = galaxy_v3_default_search_api_client.list(limit=1000, repository=[repo_id])

    assert resp.meta.count == 6
    repo_versions = sorted([x.repository_version for x in resp.data])
    assert repo_versions == ["1", "2", "2", "latest", "latest", "latest"]


def test_cross_repo_search_index_with_double_sync(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
    ansible_remote_collection_api_client,
    monitor_task,
):
    """Make sure indexes are created properly for incremental syncs."""

    # make the repo
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    repo_id = pulp_repo.pulp_href.split("/")[-2]

    # make a distro that points at the repository instead of a version
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "_vN",
            "base_path": pulp_repo.name + "_vN",
            "repository": pulp_repo.pulp_href,
        },
    )

    # create the remote
    remote_body = gen_remote(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - name: community.molecule\n    version: 0.1.0",
        sync_dependencies=False,
    )
    # remote = ansible_remote_collection_api_client.create(remote_body)
    remote = gen_object_with_cleanup(ansible_remote_collection_api_client, remote_body)

    # sync against the remote
    task = ansible_repo_api_client.sync(pulp_repo.pulp_href, {"remote": remote.pulp_href})
    monitor_task(task.task)

    # reconfigure the remote with a different collection
    col2 = "collections:\n  - name: geerlingguy.mac\n    version: 1.0.0"
    remote_body_2 = copy.deepcopy(remote_body)
    remote_body_2["requirements_file"] = col2
    ansible_remote_collection_api_client.update(remote.pulp_href, remote_body_2)

    # sync again with new config
    task = ansible_repo_api_client.sync(pulp_repo.pulp_href, {"remote": remote.pulp_href})
    monitor_task(task.task)

    resp = galaxy_v3_default_search_api_client.list(limit=1000, repository=[repo_id])
    assert resp.meta.count == 2


def test_cross_repo_search_index_on_distro_no_repo_version_and_removed_cv(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
    monitor_task,
):
    """Make sure a removed CV doesn't show up."""
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})

    # make a distro that points only at the repo ...
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository": pulp_repo.pulp_href,
        },
    )

    cv = build_and_upload_collection(ansible_repo=pulp_repo)
    # make sure the CV was indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now remove the CV from the repo
    payload = {"remove_content_units": [cv[1]]}
    res = monitor_task(ansible_repo_api_client.modify(pulp_repo.pulp_href, payload).task)
    assert res.state == "completed"

    # make sure the CV is not indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_deleted_distro(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
    monitor_task,
):
    """Make sure a deleted distro triggers an index cleanup."""
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})

    # make a distro that points only at the repo ...
    distro = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository": pulp_repo.pulp_href,
        },
    )

    # upload a CV
    build_and_upload_collection(ansible_repo=pulp_repo)

    # make sure the CV was indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now delete the distro ...
    ansible_distro_api_client.delete(distro.pulp_href)

    # make sure the CV is not indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_deleted_distro_with_another_still_remaining(
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
    monitor_task,
):
    """Make sure a deleted distro only triggers cleanup if no distros point at the repo."""
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})

    # make a distro that points only at the repo ...
    distro1 = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "1",
            "base_path": pulp_repo.name + "1",
            "repository": pulp_repo.pulp_href,
        },
    )

    # make a distro that points only at the repo ...
    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name + "2",
            "base_path": pulp_repo.name + "2",
            "repository": pulp_repo.pulp_href,
        },
    )

    # upload a CV
    build_and_upload_collection(ansible_repo=pulp_repo)

    # make sure the CV was indexed
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now delete the distro ...
    ansible_distro_api_client.delete(distro1.pulp_href)

    # make sure the CV is still indexed based on the existence of distro2 ...
    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_distribution_with_repository_and_deprecation(
    ansible_collection_deprecations_api_client,
    ansible_distro_api_client,
    ansible_repo_api_client,
    ansible_repo_version_api_client,
    build_and_upload_collection,
    galaxy_v3_collections_api_client,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
    monitor_task,
):
    """Make sure indexes are marking deprecations."""

    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})
    col = build_and_upload_collection(ansible_repo=pulp_repo)

    # make a distro that points only at the latest repo version ...
    distro = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository": pulp_repo.pulp_href,
        },
    )

    # make a deprecation
    namespace = col[0].namespace
    name = col[0].name
    monitor_task(
        galaxy_v3_collections_api_client.update(
            name,
            namespace,
            pulp_repo.name,
            {"deprecated": True},
        ).task
    )

    # make sure the CV was indexed
    dist_id = distro.pulp_href.split("/")[-2]
    resp = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp.meta.count == 1, resp

    # did it get properly marked as deprecated?
    assert resp.data[0].is_deprecated, resp


def test_cross_repo_search_index_with_updated_namespace_metadata(
    add_to_cleanup,
    ansible_distro_api_client,
    ansible_namespaces_api_client,
    ansible_repo_api_client,
    build_and_upload_collection,
    galaxy_v3_collections_api_client,
    galaxy_v3_default_search_api_client,
    galaxy_v3_plugin_namespaces_api_client,
    gen_object_with_cleanup,
    monitor_task,
    random_image_factory,
):
    """Make sure namespace metdata updates are reflected in the index."""

    # make a repo
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})

    # make a distro that points at the repository
    distro = gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository": pulp_repo.pulp_href,
        },
    )
    dist_id = distro.pulp_href.split("/")[-2]
    distro_kwargs = {"path": distro.base_path, "distro_base_path": distro.base_path}

    # define col namespace
    namespace_name = randstr()

    # define col name
    collection_name = randstr()

    # make namespace metadata
    task = galaxy_v3_plugin_namespaces_api_client.create(
        name=namespace_name, description="hello", company="Testing Co.", **distro_kwargs
    )
    result = monitor_task(task.task)
    namespace_href = [x for x in result.created_resources if "namespaces" in x][0]
    add_to_cleanup(galaxy_v3_plugin_namespaces_api_client, namespace_href)

    # make and publish a collection
    build_and_upload_collection(
        ansible_repo=pulp_repo, config={"namespace": namespace_name, "name": collection_name}
    )

    # make sure the CV was indexed
    resp = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp.meta.count == 1, resp

    # did it get all the metadata?
    cv = resp.data[0]
    assert cv.namespace_metadata.pulp_href == namespace_href
    assert cv.namespace_metadata.avatar_url is None
    # assert cv.namespace_metadata.avatar_sha256 is None
    assert cv.namespace_metadata.company == "Testing Co."
    assert cv.namespace_metadata.description == "hello"
    assert cv.namespace_metadata.name == namespace_name

    # update the namespace metadata with an avatar
    avatar_path = random_image_factory()
    task2 = galaxy_v3_plugin_namespaces_api_client.create(
        name=namespace_name,
        description="hello 2",
        company="Testing Co. redux",
        avatar=avatar_path,
        **distro_kwargs,
    )
    result2 = monitor_task(task2.task)
    namespace2_href = [x for x in result2.created_resources if "namespaces" in x][0]
    add_to_cleanup(galaxy_v3_plugin_namespaces_api_client, namespace2_href)

    # make sure the CV was re-indexed
    resp2 = galaxy_v3_default_search_api_client.list(limit=1000, distribution=[dist_id])
    assert resp2.meta.count == 1, resp2

    # did it get all the NEW metadata?
    cv2 = resp2.data[0]
    assert cv2.namespace_metadata.pulp_href == namespace2_href
    assert cv2.namespace_metadata.avatar_url is not None
    # assert cv2.namespace_metadata.avatar_sha256 is not None
    assert cv2.namespace_metadata.company == "Testing Co. redux"
    assert cv2.namespace_metadata.description == "hello 2"
    assert cv2.namespace_metadata.name == namespace_name


def test_cross_repo_search_semantic_version_ordering(
    ansible_distro_api_client,
    ansible_repo_api_client,
    build_and_upload_collection,
    galaxy_v3_default_search_api_client,
    gen_object_with_cleanup,
):
    """Make sure collections are properly sorted using the order_by='version' parameter."""
    pulp_repo = gen_object_with_cleanup(ansible_repo_api_client, {"name": str(uuid.uuid4())})

    gen_object_with_cleanup(
        ansible_distro_api_client,
        {
            "name": pulp_repo.name,
            "base_path": pulp_repo.name,
            "repository": pulp_repo.pulp_href,
        },
    )

    versions = [
        "2.0.0",
        "1.22.2",
        "1.22.1",
        "1.22.1-rc",
        "1.22.1-pre",
        "1.22.1-dev",
        "1.22.1-beta",
        "1.22.1-alpha",
        "1.1.0",
        "1.0.1",
        "1.0.0",
    ]

    for version in versions:
        build_and_upload_collection(ansible_repo=pulp_repo, config={"version": version})

    resp = galaxy_v3_default_search_api_client.list(
        limit=1000, order_by=["-version"], repository_name=[pulp_repo.name]
    )

    built_collection_versions = [col.collection_version.version for col in resp.data]

    # Make sure versions are correctly sorted according to Semantic Versioning.
    assert versions == sorted(versions, key=Version, reverse=True)

    assert versions == built_collection_versions
