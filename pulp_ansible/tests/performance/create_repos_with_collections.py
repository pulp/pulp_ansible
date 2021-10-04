import argparse

import django

django.setup()

from pulpcore.plugin.tasking import (  # noqa otherwise E402: module level not at top of file
    dispatch,
)

from pulp_ansible.app.tasks.test_tasks import (  # noqa otherwise E402: module level not at top of file
    create_repos_with_collections,
)


parser = argparse.ArgumentParser(
    description="Create Repositories with Collections and several " "RepositoryVersions."
)

parser.add_argument(
    "--num-repos",
    metavar="N",
    type=int,
    nargs=1,
    default=[50000],
    help="The number of Ansible Repositories to create.",
)

parser.add_argument(
    "--num-repo-versions-per-repo",
    metavar="N",
    type=int,
    nargs=1,
    default=[10],
    help="The number of RepositoryVersions to create per Repository.",
)

parser.add_argument(
    "--batch-size",
    metavar="N",
    type=int,
    nargs=1,
    default=[1000],
    help="The number of Ansible Repositories to create per batch.",
)

parser.add_argument(
    "--collection-percentage",
    metavar="PERCENT",
    type=float,
    nargs=1,
    default=[0.9],
    help="The percentage of collections each Repository should "
    "contain. For example 0.9 would have 90% of all collections"
    "in Pulp be associated with each repository. Collections "
    "are selected at random.",
)

args = parser.parse_args()


if __name__ == "__main__":
    repos_to_still_make = args.num_repos[0]
    num_repo_versions_per_repo = args.num_repo_versions_per_repo[0]
    collection_percentage = args.collection_percentage[0]

    while repos_to_still_make > 0:
        if repos_to_still_make >= args.batch_size[0]:
            task_args = (args.batch_size[0], num_repo_versions_per_repo, collection_percentage)
            async_result = dispatch(create_repos_with_collections, args=task_args)
            print("Dispatched task with {} repositories".format(args.batch_size[0]))
            repos_to_still_make = repos_to_still_make - args.batch_size[0]
        else:
            task_args = (repos_to_still_make, num_repo_versions_per_repo, collection_percentage)
            async_result = dispatch(create_repos_with_collections, args=task_args)
            print("Dispatched task with {} repositories".format(repos_to_still_make))
            repos_to_still_make = 0
