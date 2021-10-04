import fileinput
import math
import os
import random
import shutil
import string
import subprocess
import uuid

from django.db import IntegrityError
from pulpcore.plugin.models import Artifact
from pulpcore.plugin.tasking import dispatch

from pulp_ansible.app.models import AnsibleRepository, CollectionVersion
from pulp_ansible.app.tasks.collections import import_collection


def create_namespace(base_path, collection_n=20, versions_per_collection=5):
    """
    This will generate multiple collections tarballs all with the same namespace.

    This generates `collection_n` collections with random names, and `versions_per_collection`
    number of versions per collection.  By default it makes 20 collections with 5 versions each for
    a total of 100 tarballs with its defaults.

    The versions are 1.0.0, 2.0.0, 3.0.0, ..., etc.

    Args:
        base_path: The file path to write the collections to, e.g. `/home/vagrant/collections`
        collection_n: The number of collections to generate for this namespace
        versions_per_collection: The number of versions per collection

    """
    namespace_name = "".join([random.choice(string.ascii_lowercase) for i in range(26)])
    for collection_i in range(collection_n):
        collection_name = "".join([random.choice(string.ascii_lowercase) for i in range(26)])
        for version_i in range(versions_per_collection):
            version = str(version_i + 1) + ".0.0"

            cmd = "ansible-galaxy collection init --force --init-path {} {}.{}".format(
                base_path, namespace_name, collection_name
            )
            subprocess.run(cmd.split())

            path_to_namespace_dir = os.path.join(base_path, namespace_name)
            path_to_collection_dir = os.path.join(base_path, namespace_name, collection_name)
            galaxy_yml_path = os.path.join(path_to_collection_dir, "galaxy.yml")
            with fileinput.FileInput(galaxy_yml_path, inplace=True) as file:
                for line in file:
                    print(line.replace("1.0.0", version), end="")

            cmd = "ansible-galaxy collection build --output-path {} {}".format(
                base_path, path_to_collection_dir
            )
            subprocess.run(cmd.split())

            shutil.rmtree(path_to_namespace_dir)  # Remove the collection build dir


def import_collection_from_path(path):
    """
    Import a single collection by path.

    This method will not fail if the Artifact already exists.

    Args:
        path: The path to the tarball to import.

    """
    artifact = Artifact.init_and_validate(path)

    try:
        artifact.save()
    except IntegrityError:
        artifact = Artifact.objects.get(sha256=artifact.sha256)

    import_collection(artifact.pk)


def create_repos_with_collections(repo_count, num_repo_versions, collection_percentage):
    """
    Create repositories with a few RepositoryVersions containing existing CollectionVersions.

    This is designed to load a Pulp system with `repo_count` repositories and `num_repo_version` of
    repository versions in each. The content is already existing CollectionVersion objects.

    You specify the percentage of existing CollectionVersion objects using the
    `collection_percentage` argument. This needs to be between 0.0 and 1.0, e.g. 0.9 will select a
    random 90% of all CollectionVersions in each RepositoryVersion it creates.

    Args:
        repo_count: The number of repositories to make.
        num_repo_versions: The number of RepsitoryVersion objects per repository to make.
        collection_percentage: The float between 0.0 and 1.0 of the percentage of CollectionVersion
            objects to use in each RepositoryVersion. For example, 0.9 would have a random 90% of
            CollectionVersion objects in each RepositoryVersion it creates.

    """
    content_pk = [i for i in CollectionVersion.objects.values_list("pk", flat=True)]
    last_content_index = math.floor(collection_percentage * len(content_pk))

    for repository_i in range(repo_count):
        repository, created = AnsibleRepository.objects.get_or_create(name=uuid.uuid4())

        for version_i in range(num_repo_versions):
            random.shuffle(content_pk)
            with repository.new_version() as new_version:
                qs = CollectionVersion.objects.filter(pk__in=content_pk[:last_content_index])
                new_version.add_content(qs)


def promote_content(repos_per_task, num_repos_to_update):
    """
    Select a random CollectionVersion and attempt to add it to some number of AnsibleRepositories.

    By default this will update all Repositories, creating a new RepositoryVersion on each. The
    `num_repos_to_update` argument can specify the number of Repositories to update.

    This task generates many subtasks. This task randomly selects the Repositories it will update,
    and randomly selects the CollectionVersion. Then it dispatches N repositories to be handled by
    the `add_content_to_repositories` task. The dispatch locks on all repositories in the set to
    make this workload safe for execution with any other Pulp workload.

    The `repos_per_task` argument controls the number of repositories handled per subtask.

    Args:
        repos_per_task: The number of repositories to handle in each subtask. 100 is a typical
            choice.
        num_repos_to_update: The total number of repositories to update.

    """
    random_collection_version = CollectionVersion.objects.order_by("?").first()
    repos_to_dispatch = []
    locks = []
    for repo_num, repo in enumerate(AnsibleRepository.objects.all(), 1):
        if repo_num > num_repos_to_update:
            break
        repos_to_dispatch.append(repo.pk)
        locks.append(repo)
        if len(repos_to_dispatch) == repos_per_task:
            task_args = (random_collection_version.pk, repos_to_dispatch)
            dispatch(add_content_to_repositories, exclusive_resources=locks, args=task_args)
            repos_to_dispatch = []
            locks = []

    if repos_to_dispatch:
        task_args = (random_collection_version.pk, repos_to_dispatch)
        dispatch(add_content_to_repositories, exclusive_resources=locks, args=task_args)


def add_content_to_repositories(collection_version_pk, repositories_pks):
    """
    Add a CollectionVersion to many repositories.

    Args:
        collection_version_pk: The pk of the CollectionVersion to add to each repository.
        repositories_pks: The pks of the AnsibleRepository to add the CollectionVersion to.

    """
    for repository in AnsibleRepository.objects.filter(pk__in=repositories_pks):
        with repository.new_version() as new_version:
            qs = CollectionVersion.objects.filter(pk=collection_version_pk)
            new_version.add_content(qs)
