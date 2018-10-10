import os
import re
import tarfile
import uuid

from pulpcore.plugin.models import Artifact, ProgressBar, Repository, RepositoryVersion

from pulp_ansible.app.models import AnsibleRole, AnsibleRoleVersion


def import_content_from_tarball(namespace, artifact_pk=None, repository_pk=None):
    """
    Import Ansible content from a tarball saved as an Artifact.

    The artifact is only a temporary storage area, and is deleted after being analyzed for more
    content. Currently this task correctly handles: AnsibleRole and AnsibleRoleVersion content.

    Args:
        namespace (str): The namespace for any Ansible content to create
        artifact_pk (int): The pk of the tarball Artifact to analyze and then delete
        repository_pk (int): The repository that all created content should be associated with.
    """
    repository = Repository.objects.get(pk=repository_pk)
    artifact = Artifact.objects.get(pk=artifact_pk)
    role_paths = set()
    with tarfile.open(str(artifact.file), "r") as tar:
        artifact.delete()  # this artifact is only stored between the frontend and backend
        for tarinfo in tar:
            match = re.search('(.*)/(tasks|handlers|defaults|vars|files|templates|meta)/main.yml',
                              tarinfo.path)
            if match:
                # This is a role asset
                role_path = match.group(1)
                role_paths.add(role_path)

        tar.extractall()

        role_version_pks = []
        with ProgressBar(message='Importing Roles', total=len(role_paths)) as pb:
            for role_path in role_paths:
                match = re.search('(.*/)(.*)$', role_path)
                role_name = match.group(2)
                for tarinfo in tar:
                    if tarinfo.path == role_path:
                        # This is the role itself
                        assert tarinfo.isdir()
                        tarball_name = "{name}.tar.gz".format(name=role_name)
                        with tarfile.open(tarball_name, "w:gz") as newtar:
                            current_dir = os.getcwd()
                            os.chdir(match.group(1))
                            newtar.add(role_name)
                            os.chdir(current_dir)
                            full_path = os.path.abspath(tarball_name)
                        new_artifact = Artifact.init_and_validate(full_path)
                        new_artifact.save()
                        role, created = AnsibleRole.objects.get_or_create(namespace=namespace,
                                                                          name=role_name)
                        version = uuid.uuid4()
                        role_version = AnsibleRoleVersion(
                            role=role,
                            version=version
                        )
                        role_version.artifact = new_artifact
                        role_version.save()
                        role_version_pks.append(role_version.pk)
                pb.increment()
        with RepositoryVersion.create(repository) as new_version:
            qs = AnsibleRoleVersion.objects.filter(pk__in=role_version_pks)
            new_version.add_content(qs)
