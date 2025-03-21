import copy
import os
import random
from semantic_version import Version

import pytest

from pulp_ansible.tests.functional.utils import randstr


# We need to cary a copy of this fixture with extended scope for now. Regret...
@pytest.fixture(scope="session")
def ascii_armored_detached_signing_service(
    _ascii_armored_detached_signing_service_name, pulpcore_bindings
):
    return pulpcore_bindings.SigningServicesApi.list(
        name=_ascii_armored_detached_signing_service_name
    ).results[0]


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
    ansible_bindings,
    repo_names=None,
):
    """Make a mapping of repositories and their CV content."""

    repos = client_results_to_dict(ansible_bindings.RepositoriesAnsibleApi.list(limit=1000).results)
    dists = client_results_to_dict(
        ansible_bindings.DistributionsAnsibleApi.list(limit=1000).results
    )

    repository_dist_map = {}
    repository_version_dist_map = {}
    for dist, dist_info in dists.items():
        if dist_info.repository:
            repository_dist_map[dist_info.repository] = dist_info
        elif dist_info.repository_version:
            repository_version_dist_map[dist_info.repository_version] = dist_info

    if repo_names is None:
        repo_names = list(repos.keys())

    cvs = []

    # iterate repos
    for repo_name in repo_names:
        repo_info = repos[repo_name]
        repo_pulp_href = repos[repo_name].pulp_href
        repo_id = repos[repo_name].pulp_href.split("/")[-2]
        repo_latest_version = int(repo_info.latest_version_href.split("/")[-2])
        repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(
            repo_info.pulp_href, limit=1000
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
                rv_deprecations = ansible_bindings.ContentCollectionDeprecationsApi.list(
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
                rv_signatures = {
                    x.signed_collection.split("/")[-2]: x
                    for x in ansible_bindings.ContentCollectionSignaturesApi.list(
                        repository_version=repository_version.pulp_href, limit=1000
                    ).results
                }

            # get the collection versions ...
            rv_cvs = ansible_bindings.ContentCollectionVersionsApi.list(
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
                    "base_path": dist.base_path,
                    "distribution_id": dist.pulp_href.split("/")[-2],
                    "distribution_name": dist.name,
                    "distribution_repository": dist.repository,
                    "distribution_repository_version": dist.repository_version,
                    "repository_name": repo_name,
                    "repository_href": repo_info.pulp_href,
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
                    "pulp_labels": repo_info.pulp_labels or {},
                }
                if cv.tags:
                    cv_info["tags"] = [x.name for x in cv.tags]
                if rv_signatures:
                    for signature_cvid, signature_data in rv_signatures.items():
                        if signature_cvid == cv_id:
                            cv_info["signatures"].append(signature_data.pubkey_fingerprint)
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


def get_collection_versions(ansible_bindings):
    cversions = ansible_bindings.ContentCollectionVersionsApi.list(limit=1000)
    return {(x.namespace, x.name, x.version): x.pulp_href for x in cversions.results}


def client_results_to_dict(results):
    rmap = {}
    for result in results:
        rmap[result.name] = result
    return rmap


def delete_repos_and_distros(pulpcore_bindings, ansible_bindings, monitor_task, reponames=None):
    # map out existing distros
    dists = client_results_to_dict(
        ansible_bindings.DistributionsAnsibleApi.list(limit=1000).results
    )

    # map out existing repos
    repos = client_results_to_dict(ansible_bindings.RepositoriesAnsibleApi.list(limit=1000).results)

    # cleanup ...
    # for rname in sorted(set(x["repository_name"] for x in specs)):
    for rname in reponames:
        # clean the dist
        if rname in dists:
            ansible_bindings.DistributionsAnsibleApi.delete(dists[rname].pulp_href)

        # clean the repo
        if rname in repos:
            ansible_bindings.RepositoriesAnsibleApi.delete(repos[rname].pulp_href)

    # cv's and artifacts should be orphaned if the repos are gone ...
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"protection_time": 0}).task)


def create_repos_and_dists(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    monitor_task,
    signing_body,
    repo_specs,
    specs,
):
    created_repos = {}

    # create repo & distro ...
    for ids, spec in enumerate(specs):
        # make the repo
        if (name := spec["repository_name"]) not in created_repos:
            repo_data = {"name": name}
            if pulp_labels := repo_specs.get(name, {}).get("pulp_labels"):
                repo_data["pulp_labels"] = pulp_labels

            repository = ansible_repository_factory(**repo_data)
            created_repos[name] = repository.pulp_href

            # make the distribution
            ansible_distribution_factory(name=name, base_path=name, repository=repository)

    return created_repos


@pytest.fixture(scope="class")
def search_specs(
    pulpcore_bindings,
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    ansible_collection_factory,
    signing_gpg_homedir_path,
    ascii_armored_detached_signing_service,
    monitor_task,
):
    repo_specs = REPO_SPECS
    specs = copy.deepcopy(SPECS)

    # define signing service
    signing_service = ascii_armored_detached_signing_service
    signing_body = {"signing_service": signing_service.pulp_href, "content_units": ["*"]}

    # make a place to store artifacts in between runs ...
    # artifact_cache = os.path.join(tmp_path, "artifacts")
    artifact_cache = os.path.join("/tmp", "artifacts")
    if not os.path.exists(artifact_cache):
        os.makedirs(artifact_cache)

    reponames = sorted(set([x["repository_name"] for x in specs]))

    delete_repos_and_distros(pulpcore_bindings, ansible_bindings, monitor_task, reponames=reponames)

    created_repos = create_repos_and_dists(
        ansible_bindings,
        ansible_repository_factory,
        ansible_distribution_factory,
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

        if ckey not in uploaded_artifacts:
            # upload to the repo ...
            build_spec = copy.deepcopy(spec)
            build_spec["repository"] = "https://github.com/foo/bar"
            cv_fn = ansible_collection_factory(config=build_spec).filename
            specs[ids]["artifact"] = cv_fn
            body = {
                "file": cv_fn,
                "repository": created_repos[spec["repository_name"]],
            }
            res = monitor_task(ansible_bindings.ContentCollectionVersionsApi.create(**body).task)
            assert res.state == "completed"
            uploaded_artifacts[ckey] = cv_fn

        else:
            # copy to the repo ...
            # https://docs.pulpproject.org/pulp_rpm/workflows/copy.html
            repo_href = created_repos[spec["repository_name"]]
            cvs = get_collection_versions(ansible_bindings)
            payload = {"add_content_units": [cvs[ckey]]}
            res = monitor_task(
                ansible_bindings.RepositoriesAnsibleApi.modify(repo_href, payload).task
            )
            assert res.state == "completed"

        # sign it ...
        if spec.get("signed"):
            cvs = get_collection_versions(ansible_bindings)
            ckey = (spec["namespace"], spec["name"], spec["version"])
            repo_href = created_repos[spec["repository_name"]]
            body = {
                "content_units": [cvs[ckey]],
                "signing_service": ascii_armored_detached_signing_service.pulp_href,
            }
            res = monitor_task(ansible_bindings.RepositoriesAnsibleApi.sign(repo_href, body).task)
            assert res.state == "completed"

    # delete distributions so that some repos can hold CVs but not be "distributed"
    current_dists = ansible_bindings.DistributionsAnsibleApi.list().results
    current_dists = dict((x.name, x) for x in current_dists)
    distros_deleted = []
    for spec in specs:
        if not spec.get("has_distribution", True):
            dname = spec["repository_name"]
            if dname in distros_deleted:
                continue
            ansible_bindings.DistributionsAnsibleApi.delete(current_dists[dname].pulp_href)
            distros_deleted.append(dname)

    # limit our actions to only the repos under test ...
    reponames = sorted(set([x["repository_name"] for x in specs]))

    # remove stuff -after- it's copied around ...
    for ids, spec in enumerate(specs):
        if spec.get("removed") or spec.get("readded"):
            cvs = get_collection_versions(ansible_bindings)
            ckey = (spec["namespace"], spec["name"], spec["version"])
            repo_href = created_repos[spec["repository_name"]]

            payload = {"remove_content_units": [cvs[ckey]]}
            res = monitor_task(
                ansible_bindings.RepositoriesAnsibleApi.modify(repo_href, payload).task
            )
            assert res.state == "completed"

    # re-add stuff
    for ids, spec in enumerate(specs):
        if spec.get("readded"):
            cvs = get_collection_versions(ansible_bindings)
            ckey = (spec["namespace"], spec["name"], spec["version"])
            repo_href = created_repos[spec["repository_name"]]

            payload = {"add_content_units": [cvs[ckey]]}
            res = monitor_task(
                ansible_bindings.RepositoriesAnsibleApi.modify(repo_href, payload).task
            )
            assert res.state == "completed"

    # generate some new repo version numbers to ensure content shows up
    reponames = [x["repository_name"] for x in specs]
    for reponame in reponames:
        repo_href = created_repos[spec["repository_name"]]

        # what should be IN the repo already?
        candidates = [x for x in specs if x.get("repository_name") == reponame]
        candidates = [x for x in candidates if not x.get("removed") and not x.get("readded")]
        if not candidates:
            continue

        # pick one at random
        spec = random.choice(candidates)
        ckey = (spec["namespace"], spec["name"], spec["version"])
        # add it to the repo to bump the repo version and
        # validate the other CVs continue to live in "latest"
        payload = {"add_content_units": [cvs[ckey]]}
        res = monitor_task(ansible_bindings.RepositoriesAnsibleApi.modify(repo_href, payload).task)
        assert res.state == "completed"

    # make some deprecations ...
    for ids, spec in enumerate(specs):
        if spec.get("deprecated"):
            result = monitor_task(
                ansible_bindings.PulpAnsibleApiV3CollectionsApi.update(
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
    new_specs = get_collection_versions_by_repo(ansible_bindings, repo_names=reponames)

    return new_specs


class TestCrossRepoSearchFilters:
    """Validate the cross repo search endpoint filters."""

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

    def test_collection_version_search_all(self, ansible_bindings, search_specs):
        """Get everything."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            [],
            {},
        )

    def test_collection_version_search_by_pulp_label(self, ansible_bindings, search_specs):
        """Filter by the existence of a label on the repo"""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["'special' in spec['pulp_labels']"],
            {"repository_label": "special"},
        )

    def test_collection_version_search_by_pulp_label_value(self, ansible_bindings, search_specs):
        """Filter by the value of a label on a repo."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec['pulp_labels']['galaxy_type'] == 'sync_repo'"],
            {"repository_label": "galaxy_type=sync_repo"},
        )

    def test_collection_version_search_by_repoid(self, ansible_bindings, search_specs):
        """Get everything (but with repoids)."""
        # reduce to just 2 repos
        repo_ids = sorted(set([x["repository_id"] for x in search_specs]))
        repo_ids = repo_ids[:2]
        repo_ids_str = ",".join(["'" + x + "'" for x in repo_ids])

        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            [f"spec['repository_id'] in [{repo_ids_str}]"],
            {"repository": repo_ids},
        )

    def test_collection_version_search_by_base_path(self, ansible_bindings, search_specs):
        """Get everything (by distribution base path)."""
        base_paths = sorted(set([x["base_path"] for x in search_specs if x.get("base_path")]))
        base_paths = base_paths[:2]
        base_paths_str = ",".join(["'" + x + "'" for x in base_paths])

        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            [f"spec['base_path'] in [{base_paths_str}]"],
            {"distribution_base_path": base_paths},
        )

    def test_collection_version_search_by_distid(self, ansible_bindings, search_specs):
        """Get everything (but with distids)."""
        dist_ids = sorted(set([x["distribution_id"] for x in search_specs]))
        dist_ids = dist_ids[:2]
        dist_ids_str = ",".join(["'" + x + "'" for x in dist_ids])

        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            [f"spec['distribution_id'] in [{dist_ids_str}]"],
            {"distribution": dist_ids},
        )

    def test_collection_version_search_by_namespace(self, ansible_bindings, search_specs):
        """Get only CV's in a specific namespace."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec['namespace']['name'] == 'foo'"],
            {"namespace": "foo"},
        )

    def test_collection_version_search_by_name(self, ansible_bindings, search_specs):
        """Get only CV's with a specific name."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec['name'] == 'bellz'"],
            {"name": "bellz"},
        )

    def test_collection_version_search_by_highest(self, ansible_bindings, search_specs):
        """Get only CV's that are the highest version."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec.get('highest') is True or spec.get('is_highest') is True"],
            {"highest": True},
        )

    def test_collection_version_search_by_q(self, ansible_bindings, search_specs):
        """Get only CV's with that match a keyword by the q param."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["'gifts' in spec['tags']"],
            {"q": "gifts"},
        )

    def test_collection_version_search_by_keywords(self, ansible_bindings, search_specs):
        """Get only CV's with that match a keyword by the keyword param."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["'gifts' in spec['tags']"],
            {"keywords": "gifts"},
        )

    def test_collection_version_search_by_dependency(self, ansible_bindings, search_specs):
        """Get only CV's with that have a specific dependency."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["'foo.bar' in spec['dependencies']"],
            {"dependency": "foo.bar"},
        )

    def test_collection_version_search_by_version(self, ansible_bindings, search_specs):
        """Get only CV's with that have a specific version."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec['version'] == '1.0.1'"],
            {"version": "1.0.1"},
        )

    def test_collection_version_search_by_deprecated(self, ansible_bindings, search_specs):
        """Get only CV's that are deprecated."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec['deprecated'] == True"],
            {"deprecated": True},
        )

    def test_collection_version_search_by_not_deprecated(self, ansible_bindings, search_specs):
        """Get only CV's that are not deprecated."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["not spec.get('deprecated')"],
            {"deprecated": False},
        )

    def test_collection_version_search_by_signed(self, ansible_bindings, search_specs):
        """Get only CV's that are signed."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["spec.get('signed') is True"],
            {"signed": True},
        )

    def test_collection_version_search_by_not_signed(self, ansible_bindings, search_specs):
        """Get only CV's that are not signed."""
        self._run_search(
            ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi,
            search_specs,
            ["not spec.get('signed')"],
            {"signed": False},
        )


def test_cross_repo_search_index_on_distribution_without_repository(
    ansible_bindings, ansible_distribution_factory
):
    """Make sure no indexes are created for a repo-less distribution."""
    distribution = ansible_distribution_factory()
    distribution_id = distribution.pulp_href.split("/")[-2]
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, distribution=[distribution_id]
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_distribution_with_repository_latest_version(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure indexes are created for a distribution that points at a repo version."""

    repository = ansible_repository_factory()
    build_and_upload_collection(ansible_repo=repository)

    # get the latest repo version ...
    repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(repository.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    distro = ansible_distribution_factory(
        name=repository.name,
        base_path=repository.name,
        repository_version=repository_version_latest.pulp_href,
    )

    # make sure the CV was indexed
    dist_id = distro.pulp_href.split("/")[-2]
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, distribution=[dist_id]
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_distribution_with_repository_previous_version(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure indexes are created for a distribution that points at the latest repo version."""

    repository = ansible_repository_factory()
    build_and_upload_collection(ansible_repo=repository)

    # get the latest repo version ...
    repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(repository.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    distro = ansible_distribution_factory(
        name=repository.name,
        base_path=repository.name,
        repository_version=repository_version_latest.pulp_href,
    )

    # make sure the CV was indexed
    dist_id = distro.pulp_href.split("/")[-2]
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, distribution=[dist_id]
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_repository_without_distribution(
    ansible_bindings,
    ansible_repository_factory,
    build_and_upload_collection,
):
    """Make sure no indexes are created for a repo without a distribution."""

    repository = ansible_repository_factory()
    build_and_upload_collection(ansible_repo=repository)

    # make sure nothing was indexed
    repo_id = repository.pulp_href.split("/")[-2]
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository=[repo_id]
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_repository_version_latest_filter(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure 'latest' is acceptable as a repo version filter string."""
    repository = ansible_repository_factory()
    build_and_upload_collection(ansible_repo=repository)

    # get the latest repo version ...
    repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(repository.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points only at the latest repo version ...
    ansible_distribution_factory(
        name=repository.name,
        base_path=repository.name,
        repository_version=repository_version_latest.pulp_href,
    )

    # make sure the CV was indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[repository.name], repository_version="latest"
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_multi_distro_single_repo(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure indexes are created for a repo with multiple distributions."""

    build_config = {
        "namespace": randstr(),
        "name": randstr(),
        "version": "1.0.1",
    }

    # make the repo
    pulp_repo = ansible_repository_factory()
    repo_id = pulp_repo.pulp_href.split("/")[-2]

    # add a collection to bump the version number
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # get the latest repo version ...
    repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points at the first version
    ansible_distribution_factory(
        name=pulp_repo.name + "_v1",
        base_path=pulp_repo.name + "_v1",
        repository_version=repository_version_latest.pulp_href,
    )

    # we should now have 1 index
    # repov1 + cv1

    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository=[repo_id]
    )
    assert resp.meta.count == 1
    assert resp.data[0].repository_version == "1"

    # add a collection to bump the version number
    build_config["version"] = "1.0.2"
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # get the latest repo version ...
    repository_versions = ansible_bindings.RepositoriesAnsibleVersionsApi.list(pulp_repo.pulp_href)
    repository_version_latest = repository_versions.results[0]

    # make a distro that points at the second version
    ansible_distribution_factory(
        name=pulp_repo.name + "_v2",
        base_path=pulp_repo.name + "_v2",
        repository_version=repository_version_latest.pulp_href,
    )

    # per david, we should have 3 entries now
    # repov1+cv1
    # repov2+cv1
    # repov2+cv2

    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository=[repo_id]
    )
    assert resp.meta.count == 3
    repo_versions = sorted([int(x.repository_version) for x in resp.data])
    assert repo_versions == [1, 2, 2]

    # add a collection to bump the version number
    build_config["version"] = "1.0.3"
    build_and_upload_collection(ansible_repo=pulp_repo, config=build_config)

    # make a distro that points at the repository instead of a version
    ansible_distribution_factory(
        name=pulp_repo.name + "_vN",
        base_path=pulp_repo.name + "_vN",
        repository=pulp_repo,
    )

    # per david, we should have 6 entries now
    # repov=1 + cv1
    # repov=2 + cv1,cv2
    # repov=null + cv1,cv2,cv3

    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository=[repo_id]
    )

    assert resp.meta.count == 6
    repo_versions = sorted([x.repository_version for x in resp.data])
    assert repo_versions == ["1", "2", "2", "latest", "latest", "latest"]


def test_cross_repo_search_index_with_double_sync(
    ansible_bindings,
    ansible_collection_remote_factory,
    ansible_sync_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure indexes are created properly for incremental syncs."""

    # create the remote
    remote = ansible_collection_remote_factory(
        url="https://galaxy.ansible.com",
        requirements_file="collections:\n  - name: community.molecule\n    version: 0.1.0",
        sync_dependencies=False,
    )

    # sync into a repository
    repository = ansible_sync_factory(remote=remote.pulp_href)
    repository_id = repository.pulp_href.split("/")[-2]

    # make a distro that points at the repository instead of a version
    ansible_distribution_factory(
        name=repository.name + "_vN",
        base_path=repository.name + "_vN",
        repository=repository,
    )

    # reconfigure the remote with a different collection
    ansible_bindings.RemotesCollectionApi.partial_update(
        remote.pulp_href,
        {"requirements_file": "collections:\n  - name: geerlingguy.mac\n    version: 1.0.0"},
    )

    # sync again with new config
    repository = ansible_sync_factory(ansible_repo=repository, remote=remote.pulp_href)
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository=[repository_id]
    )
    assert resp.meta.count == 2


def test_cross_repo_search_index_on_distro_no_repo_version_and_removed_cv(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Make sure a removed CV doesn't show up."""
    repository = ansible_repository_factory()

    # make a distro that points only at the repo ...
    ansible_distribution_factory(
        name=repository.name,
        base_path=repository.name,
        repository=repository,
    )

    cv = build_and_upload_collection(ansible_repo=repository)

    # make sure the CV was indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[repository.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now remove the CV from the repo
    payload = {"remove_content_units": [cv[1]]}
    res = monitor_task(
        ansible_bindings.RepositoriesAnsibleApi.modify(repository.pulp_href, payload).task
    )
    assert res.state == "completed"

    # make sure the CV is not indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[repository.name], repository_version="latest"
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_deleted_distro(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Make sure a deleted distro triggers an index cleanup."""
    pulp_repo = ansible_repository_factory()

    distro = ansible_distribution_factory(
        name=pulp_repo.name,
        base_path=pulp_repo.name,
        repository=pulp_repo,
    )

    # upload a CV
    build_and_upload_collection(ansible_repo=pulp_repo)

    # make sure the CV was indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now delete the distro ...
    monitor_task(ansible_bindings.DistributionsAnsibleApi.delete(distro.pulp_href).task)

    # make sure the CV is not indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 0


def test_cross_repo_search_index_on_deleted_distro_with_another_still_remaining(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Make sure a deleted distro only triggers cleanup if no distros point at the repo."""
    pulp_repo = ansible_repository_factory()

    distro1 = ansible_distribution_factory(
        name=pulp_repo.name + "1",
        base_path=pulp_repo.name + "1",
        repository=pulp_repo,
    )

    ansible_distribution_factory(
        name=pulp_repo.name + "2",
        base_path=pulp_repo.name + "2",
        repository=pulp_repo,
    )

    # upload a CV
    build_and_upload_collection(ansible_repo=pulp_repo)

    # make sure the CV was indexed
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1

    # now delete the distro ...
    monitor_task(ansible_bindings.DistributionsAnsibleApi.delete(distro1.pulp_href).task)

    # make sure the CV is still indexed based on the existence of distro2 ...
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, repository_name=[pulp_repo.name], repository_version="latest"
    )
    assert resp.meta.count == 1


def test_cross_repo_search_index_on_distribution_with_repository_and_deprecation(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
    monitor_task,
):
    """Make sure indexes are marking deprecations."""

    repository = ansible_repository_factory()
    collection = build_and_upload_collection(ansible_repo=repository)

    # make a distribution that points only at the latest repo version ...
    distribution = ansible_distribution_factory(
        name=repository.name, base_path=repository.name, repository=repository
    )

    # make a deprecation
    namespace = collection[0].namespace
    name = collection[0].name
    monitor_task(
        ansible_bindings.PulpAnsibleApiV3CollectionsApi.update(
            name,
            namespace,
            repository.name,
            {"deprecated": True},
        ).task
    )

    # make sure the CV was indexed
    distribution_id = distribution.pulp_href.split("/")[-2]
    resp = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
        limit=1000, distribution=[distribution_id]
    )
    assert resp.meta.count == 1, resp

    # did it get properly marked as deprecated?
    assert resp.data[0].is_deprecated, resp


def test_cross_repo_search_index_with_updated_namespace_metadata(
    add_to_cleanup,
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
    monitor_task,
    random_image_factory,
):
    """Make sure namespace metdata updates are reflected in the index."""

    repository = ansible_repository_factory()
    name = repository.name
    distribution = ansible_distribution_factory(name=name, base_path=name, repository=repository)

    dist_id = distribution.pulp_href.split("/")[-2]
    distribution_kwargs = {"path": name, "distro_base_path": name}

    # define col namespace
    namespace_name = randstr()

    # define col name
    collection_name = randstr()

    # make namespace metadata
    task = ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi.create(
        name=namespace_name, description="hello", company="Testing Co.", **distribution_kwargs
    )
    result = monitor_task(task.task)
    namespace_href = [x for x in result.created_resources if "namespaces" in x][0]
    add_to_cleanup(
        ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi, namespace_href
    )

    # make and publish a collection
    build_and_upload_collection(
        ansible_repo=repository, config={"namespace": namespace_name, "name": collection_name}
    )

    # make sure the CV was indexed
    response = (
        ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
            limit=1000, distribution=[dist_id]
        )
    )
    assert response.meta.count == 1, response

    # did it get all the metadata?
    cv = response.data[0]
    assert cv.namespace_metadata.pulp_href == namespace_href
    assert cv.namespace_metadata.avatar_url is None
    # assert cv.namespace_metadata.avatar_sha256 is None
    assert cv.namespace_metadata.company == "Testing Co."
    assert cv.namespace_metadata.description == "hello"
    assert cv.namespace_metadata.name == namespace_name

    # update the namespace metadata with an avatar
    avatar_path = random_image_factory()
    task2 = ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi.create(
        name=namespace_name,
        description="hello 2",
        company="Testing Co. redux",
        avatar=str(avatar_path),
        **distribution_kwargs,
    )
    result2 = monitor_task(task2.task)
    namespace2_href = [x for x in result2.created_resources if "namespaces" in x][0]
    add_to_cleanup(
        ansible_bindings.PulpAnsibleApiV3PluginAnsibleContentNamespacesApi, namespace2_href
    )

    # make sure the CV was re-indexed
    response2 = (
        ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
            limit=1000, distribution=[dist_id]
        )
    )
    assert response2.meta.count == 1, response2

    # did it get all the NEW metadata?
    cv2 = response2.data[0]
    assert cv2.namespace_metadata.pulp_href == namespace2_href
    assert cv2.namespace_metadata.avatar_url is not None
    # assert cv2.namespace_metadata.avatar_sha256 is not None
    assert cv2.namespace_metadata.company == "Testing Co. redux"
    assert cv2.namespace_metadata.description == "hello 2"
    assert cv2.namespace_metadata.name == namespace_name


def test_cross_repo_search_semantic_version_ordering(
    ansible_bindings,
    ansible_repository_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Make sure collections are properly sorted using the order_by='version' parameter."""
    repository = ansible_repository_factory()
    name = repository.name
    ansible_distribution_factory(name=name, base_path=name, repository=repository)

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
    # Make sure versions are correctly sorted according to Semantic Versioning.
    assert versions == sorted(versions, key=Version, reverse=True)

    for version in versions:
        build_and_upload_collection(ansible_repo=repository, config={"version": version})

    response = (
        ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleSearchCollectionVersionsApi.list(
            limit=1000, order_by=["-version"], repository_name=[name]
        )
    )

    built_collection_versions = [col.collection_version.version for col in response.data]

    assert versions == built_collection_versions
