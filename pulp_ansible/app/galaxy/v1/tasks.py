import os
import shutil
import subprocess
import tempfile

from django.db import transaction

from pulpcore.plugin.models import Artifact
from pulpcore.plugin.models import ContentArtifact
from pulpcore.plugin.tasking import add_and_remove

"""
from pulp_ansible.app.galaxy.v1.utils import (
    get_role_version,
    # get_tag_commit_hash,
    # get_tag_commit_date,
    # get_path_role_meta
)
"""

# from pulp_ansible.app.galaxy.v1.constants import LEGACY_REPOSITORY_NAME

from pulp_ansible.app.models import AnsibleRepository, Role

# from pulp_ansible.app.tasks.roles import GITHUB_URL

# from galaxy_importer.loaders.content import RoleLoader
# from galaxy_importer.utils import markup as markup_utils

# from git import GitCommandError
from git import Repo


def legacy_role_import(*args, **kwargs):
    """
    Import a legacy role given the github user, repo and or name.
    """
    # We expect this AnsibleRepository to have been created elsewhere.
    ansible_repo_id = kwargs.get("ansible_repository")

    # This should be a valid github username
    github_user = kwargs.get("github_user")

    # This should be the actual repository name. It is rarely 1:1.
    github_repo = kwargs.get("github_repo")

    # this is often a git tag or maybe a commit hash?
    github_reference = kwargs.get("github_reference")

    # We do not want an empty string for the github reference
    if github_reference is not None and not github_reference.strip():
        github_reference = None

    # I'm not sure when the client would pass this value in.
    # repository_id = kwargs.get("repository_id")

    # The client can override the name of the role if the repo name is not relevant.
    # alternate_role_name = kwargs.get("alternate_role_name")
    role_name = kwargs.get("alternate_role_name") or github_repo.replace("ansible-role-", "")

    # Most of what we need will have to come from the checkout
    with tempfile.TemporaryDirectory() as checkout_path:

        # Clone the repo into the checkout path
        """
        clone_url = f"https://github.com/{github_user}/{github_repo}"
        cmd = f"git clone {clone_url} {checkout_path}"
        pid = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if pid.returncode != 0:
            raise Exception(pid.stdout.decode("utf-8"))
        """
        clone_url = f"https://github.com/{github_user}/{github_repo}"
        gitrepo = Repo.clone_from(clone_url, checkout_path, multi_options=["--recurse-submodules"])

        # use the reference to set the version or enumerate it via the util function
        if github_reference is not None:
            # cmd = f"git -c advice.detachedHead=false checkout tags/{github_reference}"
            # pid = subprocess.run(cmd, shell=True, cwd=checkout_path)
            gitrepo.checkout(github_reference)
        else:
            """
            github_reference = get_role_version(
                checkout_path=checkout_path,
                github_user=github_user,
                github_repo=github_repo,
                github_reference=github_reference,
                alternate_role_name=alternate_role_name,
            )
            """
            if gitrepo.tags:
                github_reference = gitrepo.tags[-1].name

        """
        # if no tags, default to the commit hash?
        # WARNING: many roles upstream have -no- versions.
        if github_reference is None:
            github_reference = gitrepo.head.commit.hexsha
        """

        # Upstream stores this, pulp_ansible does not.
        # github_commit = get_tag_commit_hash(
        #     clone_url, github_reference, checkout_path=checkout_path
        # )

        # Upstream stores this as a "release date", pulp_ansible does not.
        # github_commit_date = get_tag_commit_date(
        #     clone_url, github_reference, checkout_path=checkout_path
        # )

        # pulp_ansible does not have role tags
        """
        # parse out the role metadata
        role_meta = get_path_role_meta(checkout_path)
        role_tags = role_meta.get("galaxy_info", {}).get("galaxy_tags", [])
        if role_tags is None:
            role_tags = []
        """

        # pulp_ansible does not have a model or a view for readme content
        """
        ldr = RoleLoader(
            content_type="role",
            root=os.path.dirname(checkout_path),
            rel_path=os.path.basename(checkout_path),
        )
        readme = ldr._get_readme()
        readme_html = markup_utils._render_from_markdown(readme)
        """

        metadata = {
            "github_user": github_user,
            "github_repo": github_repo,
            "role_name": role_name,
            "name": role_name,
            "namespace": github_user,
            "role_version": github_reference,
        }

        # This is a pulp'ism for the source url
        # but we will generate the download_url in the
        # serializer so this wouldn't ever be
        # used ... ?
        relative_path = "%s/%s/%s.tar.gz" % (
            metadata["github_user"],
            metadata["role_name"],
            metadata["role_version"],
        )

        # Make a tarball
        shutil.rmtree(os.path.join(checkout_path, ".git"))
        tarfn = f"/tmp/{github_user}.{role_name}.{github_reference}.tar.gz"
        cmd = f"tar czvf {tarfn} {checkout_path}"
        pid = subprocess.run(cmd, shell=True)
        assert pid.returncode == 0

        """
        # pulp_ansible's Roles are actuallly Role Versions
        # The roles list viewset aggregates the versions together
        # by using a {namespace}.{name} as the primary key.
        role = Role(
            version=metadata["role_version"],
            name=metadata["name"],
            namespace=metadata["namespace"],
        )
        role.save()

        # Create a real artifact
        artifact = Artifact.init_and_validate(tarfn)
        artifact.save()

        # Use Content to tie the role and artifact together
        ca1 = ContentArtifact.objects.create(
            artifact=artifact, content=role, relative_path=relative_path
        )
        ca1.save()

        # Add the role to the legacy repository via a new version.
        legacy = AnsibleRepository.objects.get(pulp_id=ansible_repo_id)
        add_and_remove(legacy.pk, [role.pk], [])
        """

        # Create a real artifact
        artifact = Artifact.init_and_validate(tarfn)
        artifact.save()

        # Create the role and bind with the artifact as a "content artifact"
        role, content_artifact = _create_role_and_content_artifact(
            metadata, relative_path, artifact
        )

        # Add the role to the legacy repository via a new version.
        legacy = AnsibleRepository.objects.get(pulp_id=ansible_repo_id)
        add_and_remove(legacy.pk, [role.pk], [])


@transaction.atomic
def _create_role_and_content_artifact(role_metadata, relative_path, artifact):
    """
    Encapsulate database writes with a transaction.
    """
    # pulp_ansible's Roles are actuallly Role Versions
    # The roles list viewset aggregates the versions together
    # by using a {namespace}.{name} as the primary key.
    role = Role(
        version=role_metadata["role_version"],
        name=role_metadata["name"],
        namespace=role_metadata["namespace"],
    )
    role.save()

    """
    # Create a real artifact
    artifact = Artifact.init_and_validate(tarfn)
    artifact.save()
    """

    # Use Content to tie the role and artifact together
    ca1 = ContentArtifact.objects.create(
        artifact=artifact, content=role, relative_path=relative_path
    )
    ca1.save()

    """
    # Add the role to the legacy repository via a new version.
    legacy = AnsibleRepository.objects.get(pulp_id=ansible_repo_id)
    add_and_remove(legacy.pk, [role.pk], [])
    """

    return role, ca1
