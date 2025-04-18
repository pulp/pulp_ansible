import pytest
import uuid

from pulpcore.client.pulp_ansible import ApiException, AsyncOperationResponse

from pulp_ansible.tests.functional.constants import ANSIBLE_GALAXY_URL


# TODO Find a way to make the factories work with try_action
def gen_repo():
    return {"name": str(uuid.uuid4())}


def gen_distribution():
    return {"name": str(uuid.uuid4()), "base_path": str(uuid.uuid4())}


def gen_remote():
    return {"name": str(uuid.uuid4()), "url": ANSIBLE_GALAXY_URL, "rate_limit": 5}


@pytest.fixture()
def gen_users(gen_user):
    """Returns a user generator function for the tests."""

    def _gen_users(role_names=list()):
        if isinstance(role_names, str):
            role_names = [role_names]
        creator_roles = [f"ansible.{role}_creator" for role in role_names]
        viewer_roles = [f"ansible.{role}_viewer" for role in role_names]
        user_creator = gen_user(model_roles=creator_roles)
        user_reader = gen_user(model_roles=viewer_roles)
        user_helpless = gen_user()
        return user_creator, user_reader, user_helpless

    return _gen_users


@pytest.fixture()
def try_action(monitor_task):
    def _try_action(user, client, action, outcome, *args, **kwargs):
        action_api = getattr(client, f"{action}_with_http_info")
        try:
            with user:
                try:
                    data, status, _ = action_api(*args, **kwargs, _return_http_data_only=False)
                except ValueError:
                    response = action_api(*args, **kwargs)
                    data = response.data
                    status = response.status_code
            if isinstance(data, AsyncOperationResponse):
                data = monitor_task(data.task)
        except ApiException as e:
            assert e.status == outcome, f"{e}"
        else:
            assert status == outcome, f"User performed {action} when they shouldn't been able to"
            return data

    return _try_action


def test_ansible_repository_rbac(ansible_bindings, gen_users, try_action):
    user_creator, user_reader, user_helpless = gen_users("ansiblerepository")

    # List testing
    try_action(user_creator, ansible_bindings.RepositoriesAnsibleApi, "list", 200)
    try_action(user_reader, ansible_bindings.RepositoriesAnsibleApi, "list", 200)
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "list", 200)

    # Create testing
    repo = try_action(
        user_creator, ansible_bindings.RepositoriesAnsibleApi, "create", 201, gen_repo()
    )
    try_action(user_reader, ansible_bindings.RepositoriesAnsibleApi, "create", 403, gen_repo())
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "create", 403, gen_repo())

    # View testing
    try_action(user_creator, ansible_bindings.RepositoriesAnsibleApi, "read", 200, repo.pulp_href)
    try_action(user_reader, ansible_bindings.RepositoriesAnsibleApi, "read", 200, repo.pulp_href)
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "read", 404, repo.pulp_href)

    # Update testing
    update_args = [repo.pulp_href, gen_repo()]
    try_action(user_creator, ansible_bindings.RepositoriesAnsibleApi, "update", 202, *update_args)
    try_action(user_reader, ansible_bindings.RepositoriesAnsibleApi, "update", 403, *update_args)
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "update", 404, *update_args)

    # Partial update testing
    partial_update_args = [repo.pulp_href, {"name": str(uuid.uuid4())}]
    try_action(
        user_creator,
        ansible_bindings.RepositoriesAnsibleApi,
        "partial_update",
        202,
        *partial_update_args,
    )
    try_action(
        user_reader,
        ansible_bindings.RepositoriesAnsibleApi,
        "partial_update",
        403,
        *partial_update_args,
    )
    try_action(
        user_helpless,
        ansible_bindings.RepositoriesAnsibleApi,
        "partial_update",
        404,
        *partial_update_args,
    )

    # Delete testing
    try_action(user_reader, ansible_bindings.RepositoriesAnsibleApi, "delete", 403, repo.pulp_href)
    try_action(
        user_helpless, ansible_bindings.RepositoriesAnsibleApi, "delete", 404, repo.pulp_href
    )
    try_action(user_creator, ansible_bindings.RepositoriesAnsibleApi, "delete", 202, repo.pulp_href)


def test_ansible_repository_version_repair(
    ansible_bindings,
    ansible_repo_factory,
    gen_users,
    try_action,
):
    """Test the repository version repair action"""
    user_creator, user_reader, user_helpless = gen_users("ansiblerepository")

    with user_creator:
        repo = ansible_repo_factory()
        ver_href = repo.latest_version_href
    body = {"verify_checksums": True}
    try_action(
        user_creator, ansible_bindings.RepositoriesAnsibleVersionsApi, "repair", 202, ver_href, body
    )
    try_action(
        user_reader, ansible_bindings.RepositoriesAnsibleVersionsApi, "repair", 403, ver_href, body
    )
    try_action(
        user_helpless,
        ansible_bindings.RepositoriesAnsibleVersionsApi,
        "repair",
        403,
        ver_href,
        body,
    )


def test_repository_apis(
    ansible_bindings,
    ansible_collection_remote_factory,
    ansible_repo_factory,
    gen_users,
    try_action,
):
    """Test repository specific actions, modify, sync and rebuild_metadata."""
    user_creator, user_reader, user_helpless = gen_users(["ansiblerepository", "collectionremote"])

    # Sync tests
    with user_creator:
        user_creator_remote = ansible_collection_remote_factory(
            url="https://galaxy.ansible.com",
            requirements_file="collections:\n  - name: community.docker\n    version: 3.0.0",
        )
        repo = ansible_repo_factory()

    body = {"mirror": False, "optimize": True, "remote": user_creator_remote.pulp_href}
    try_action(
        user_reader, ansible_bindings.RepositoriesAnsibleApi, "sync", 403, repo.pulp_href, body
    )
    try_action(
        user_creator, ansible_bindings.RepositoriesAnsibleApi, "sync", 202, repo.pulp_href, body
    )
    try_action(
        user_helpless, ansible_bindings.RepositoriesAnsibleApi, "sync", 404, repo.pulp_href, body
    )

    # Modify tests
    try_action(
        user_reader, ansible_bindings.RepositoriesAnsibleApi, "modify", 403, repo.pulp_href, {}
    )
    try_action(
        user_creator, ansible_bindings.RepositoriesAnsibleApi, "modify", 202, repo.pulp_href, {}
    )
    try_action(
        user_helpless, ansible_bindings.RepositoriesAnsibleApi, "modify", 404, repo.pulp_href, {}
    )

    # Rebuild metadata tests
    rebuild_metadata_args = [
        repo.pulp_href,
        {"namespace": "community", "name": "docker", "version": "3.0.0"},
    ]
    try_action(
        user_reader,
        ansible_bindings.RepositoriesAnsibleApi,
        "rebuild_metadata",
        403,
        *rebuild_metadata_args,
    )
    try_action(
        user_creator,
        ansible_bindings.RepositoriesAnsibleApi,
        "rebuild_metadata",
        202,
        *rebuild_metadata_args,
    )
    try_action(
        user_helpless,
        ansible_bindings.RepositoriesAnsibleApi,
        "rebuild_metadata",
        404,
        *rebuild_metadata_args,
    )


def test_repository_role_management(ansible_bindings, gen_users, ansible_repo_factory, try_action):
    """Check repository role management apis."""
    user_creator, user_reader, user_helpless = gen_users("ansiblerepository")

    with user_creator:
        repo = ansible_repo_factory()
        href = repo.pulp_href

    # Permission check testing
    aperm_response = try_action(
        user_reader, ansible_bindings.RepositoriesAnsibleApi, "my_permissions", 200, href
    )
    assert aperm_response.permissions == []
    bperm_response = try_action(
        user_creator, ansible_bindings.RepositoriesAnsibleApi, "my_permissions", 200, href
    )
    assert len(bperm_response.permissions) > 0
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "my_permissions", 404, href)

    # Add "creator" role testing
    nested_role = {"users": [user_helpless.username], "role": "ansible.ansiblerepository_viewer"}
    try_action(
        user_reader,
        ansible_bindings.RepositoriesAnsibleApi,
        "add_role",
        403,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_helpless,
        ansible_bindings.RepositoriesAnsibleApi,
        "add_role",
        404,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_creator,
        ansible_bindings.RepositoriesAnsibleApi,
        "add_role",
        201,
        href,
        nested_role=nested_role,
    )

    # Permission check testing again
    cperm_response = try_action(
        user_helpless, ansible_bindings.RepositoriesAnsibleApi, "my_permissions", 200, href
    )
    assert len(cperm_response.permissions) == 1

    # Remove "viewer" role testing
    try_action(
        user_reader,
        ansible_bindings.RepositoriesAnsibleApi,
        "remove_role",
        403,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_helpless,
        ansible_bindings.RepositoriesAnsibleApi,
        "remove_role",
        403,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_creator,
        ansible_bindings.RepositoriesAnsibleApi,
        "remove_role",
        201,
        href,
        nested_role=nested_role,
    )

    # Permission check testing one more time
    try_action(user_helpless, ansible_bindings.RepositoriesAnsibleApi, "my_permissions", 404, href)


def test_ansible_distribution_rbac(
    ansible_bindings,
    ansible_repo_factory,
    ansible_distribution_factory,
    gen_users,
    try_action,
):
    user_creator, user_reader, user_helpless = gen_users(
        ["ansibledistribution", "ansiblerepository"]
    )

    # Create testing
    with user_creator:
        repo = ansible_repo_factory()
        distribution = ansible_distribution_factory(repo)
    try_action(
        user_reader, ansible_bindings.DistributionsAnsibleApi, "create", 403, gen_distribution()
    )
    try_action(
        user_helpless, ansible_bindings.DistributionsAnsibleApi, "create", 403, gen_distribution()
    )

    # List testing
    try_action(user_creator, ansible_bindings.DistributionsAnsibleApi, "list", 200)
    try_action(user_reader, ansible_bindings.DistributionsAnsibleApi, "list", 200)
    try_action(user_helpless, ansible_bindings.DistributionsAnsibleApi, "list", 200)

    # View testing
    view_args = [distribution.pulp_href]
    try_action(user_creator, ansible_bindings.DistributionsAnsibleApi, "read", 200, *view_args)
    try_action(user_reader, ansible_bindings.DistributionsAnsibleApi, "read", 200, *view_args)
    try_action(user_helpless, ansible_bindings.DistributionsAnsibleApi, "read", 404, *view_args)

    # Update testing
    update_args = [distribution.pulp_href, gen_distribution()]
    try_action(user_creator, ansible_bindings.DistributionsAnsibleApi, "update", 202, *update_args)
    try_action(user_reader, ansible_bindings.DistributionsAnsibleApi, "update", 403, *update_args)
    try_action(user_helpless, ansible_bindings.DistributionsAnsibleApi, "update", 404, *update_args)

    # Partial update testing
    partial_update_args = [distribution.pulp_href, {"name": str(uuid.uuid4())}]
    try_action(
        user_creator,
        ansible_bindings.DistributionsAnsibleApi,
        "partial_update",
        202,
        *partial_update_args,
    )
    try_action(
        user_reader,
        ansible_bindings.DistributionsAnsibleApi,
        "partial_update",
        403,
        *partial_update_args,
    )
    try_action(
        user_helpless,
        ansible_bindings.DistributionsAnsibleApi,
        "partial_update",
        404,
        *partial_update_args,
    )

    # Delete testing
    try_action(
        user_reader, ansible_bindings.DistributionsAnsibleApi, "delete", 403, distribution.pulp_href
    )
    try_action(
        user_helpless,
        ansible_bindings.DistributionsAnsibleApi,
        "delete",
        404,
        distribution.pulp_href,
    )
    try_action(
        user_creator,
        ansible_bindings.DistributionsAnsibleApi,
        "delete",
        202,
        distribution.pulp_href,
    )


def test_ansible_distribution_role_management(
    ansible_bindings,
    ansible_repo_factory,
    ansible_distribution_factory,
    gen_users,
    try_action,
):
    user_creator, user_reader, user_helpless = gen_users(
        ["ansibledistribution", "ansiblerepository"]
    )

    # Check role management apis
    with user_creator:
        repo = ansible_repo_factory()
        distribution = ansible_distribution_factory(repo)

    href = distribution.pulp_href

    # Permission check testing
    urperm_response = try_action(
        user_reader, ansible_bindings.DistributionsAnsibleApi, "my_permissions", 200, href
    )
    assert urperm_response.permissions == []
    ucperm_response = try_action(
        user_creator, ansible_bindings.DistributionsAnsibleApi, "my_permissions", 200, href
    )
    assert len(ucperm_response.permissions) > 0
    try_action(user_helpless, ansible_bindings.DistributionsAnsibleApi, "my_permissions", 404, href)

    # Add "creator" role testing
    nested_role = {"users": [user_reader.username], "role": "ansible.ansibledistribution_creator"}
    try_action(
        user_reader,
        ansible_bindings.DistributionsAnsibleApi,
        "add_role",
        403,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_helpless,
        ansible_bindings.DistributionsAnsibleApi,
        "add_role",
        404,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_creator,
        ansible_bindings.DistributionsAnsibleApi,
        "add_role",
        201,
        href,
        nested_role=nested_role,
    )

    # Permission check testing again
    urperm_response = try_action(
        user_reader, ansible_bindings.DistributionsAnsibleApi, "my_permissions", 200, href
    )
    assert len(urperm_response.permissions) == 1

    # Remove "viewer" role testing
    try_action(
        user_reader,
        ansible_bindings.DistributionsAnsibleApi,
        "remove_role",
        403,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_helpless,
        ansible_bindings.DistributionsAnsibleApi,
        "remove_role",
        404,
        href,
        nested_role=nested_role,
    )
    try_action(
        user_creator,
        ansible_bindings.DistributionsAnsibleApi,
        "remove_role",
        201,
        href,
        nested_role=nested_role,
    )

    # Permission check testing one more time
    urperm_response = try_action(
        user_reader, ansible_bindings.DistributionsAnsibleApi, "my_permissions", 200, href
    )
    assert len(urperm_response.permissions) == 0


REMOTES = {
    "collection": {"role_name": "collectionremote"},
    "git": {"role_name": "gitremote"},
    "role": {"role_name": "roleremote"},
}


@pytest.mark.parametrize("remote", REMOTES)
def test_remotes_rbac(
    ansible_bindings,
    gen_users,
    try_action,
    remote,
):
    REMOTE_APIS = {
        "collectionremote": ansible_bindings.RemotesCollectionApi,
        "gitremote": ansible_bindings.RemotesGitApi,
        "roleremote": ansible_bindings.RemotesRoleApi,
    }
    role_name = REMOTES[remote]["role_name"]
    remote_api = REMOTE_APIS[role_name]

    user_creator, user_reader, user_helpless = gen_users(role_name)

    # List testing
    try_action(user_creator, remote_api, "list", 200)
    try_action(user_reader, remote_api, "list", 200)
    try_action(user_helpless, remote_api, "list", 200)

    # Create testing
    remote = try_action(
        user_creator,
        remote_api,
        "create",
        201,
        gen_remote(),
    )
    try_action(
        user_reader,
        remote_api,
        "create",
        403,
        gen_remote(),
    )
    try_action(
        user_helpless,
        remote_api,
        "create",
        403,
        gen_remote(),
    )

    # View testing
    try_action(user_creator, remote_api, "read", 200, remote.pulp_href)
    try_action(user_reader, remote_api, "read", 200, remote.pulp_href)
    try_action(user_helpless, remote_api, "read", 404, remote.pulp_href)

    # Update testing
    update_args = [remote.pulp_href, gen_remote()]
    try_action(user_creator, remote_api, "update", 202, *update_args)
    try_action(user_reader, remote_api, "update", 403, *update_args)
    try_action(user_helpless, remote_api, "update", 404, *update_args)

    # Partial update testing
    partial_update_args = [remote.pulp_href, {"name": str(uuid.uuid4())}]
    try_action(user_creator, remote_api, "partial_update", 202, *partial_update_args)
    try_action(user_reader, remote_api, "partial_update", 403, *partial_update_args)
    try_action(user_helpless, remote_api, "partial_update", 404, *partial_update_args)

    # Delete testing
    try_action(user_reader, remote_api, "delete", 403, remote.pulp_href)
    try_action(user_helpless, remote_api, "delete", 404, remote.pulp_href)
    try_action(user_creator, remote_api, "delete", 202, remote.pulp_href)


@pytest.mark.parametrize("remote", REMOTES)
def test_remotes_role_management(
    ansible_bindings,
    gen_users,
    try_action,
    remote,
):
    REMOTE_APIS = {
        "collectionremote": ansible_bindings.RemotesCollectionApi,
        "gitremote": ansible_bindings.RemotesGitApi,
        "roleremote": ansible_bindings.RemotesRoleApi,
    }
    role_name = REMOTES[remote]["role_name"]
    remote_api = REMOTE_APIS[role_name]

    user_creator, user_reader, user_helpless = gen_users(role_name)

    # Check role management apis
    remote = try_action(
        user_creator,
        remote_api,
        "create",
        201,
        gen_remote(),
    )
    href = remote.pulp_href

    # Permission check testing
    urperm_response = try_action(user_reader, remote_api, "my_permissions", 200, href)
    assert urperm_response.permissions == []
    ucperm_response = try_action(user_creator, remote_api, "my_permissions", 200, href)
    assert len(ucperm_response.permissions) > 0
    try_action(user_helpless, remote_api, "my_permissions", 404, href)

    # Add "viewer" role testing
    nested_role = {"users": [user_helpless.username], "role": f"ansible.{role_name}_viewer"}
    try_action(user_reader, remote_api, "add_role", 403, href, nested_role=nested_role)
    try_action(user_helpless, remote_api, "add_role", 404, href, nested_role=nested_role)
    try_action(user_creator, remote_api, "add_role", 201, href, nested_role=nested_role)

    # Permission check testing again
    uhperm_response = try_action(user_helpless, remote_api, "my_permissions", 200, href)
    assert len(uhperm_response.permissions) == 1

    # Remove "viewer" role testing
    try_action(user_reader, remote_api, "remove_role", 403, href, nested_role=nested_role)
    try_action(user_helpless, remote_api, "remove_role", 403, href, nested_role=nested_role)
    try_action(user_creator, remote_api, "remove_role", 201, href, nested_role=nested_role)

    # Permission check testing one more time
    try_action(user_helpless, remote_api, "my_permissions", 404, href)
