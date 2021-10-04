import argparse

import django

django.setup()

from pulpcore.plugin.tasking import (  # noqa otherwise E402: module level not at top of file
    dispatch,
)

from pulp_ansible.app.tasks.test_tasks import (  # noqa otherwise E402: module level not at top of file
    promote_content,
)


parser = argparse.ArgumentParser(description="Find a collection and promote it.")

parser.add_argument(
    "--repos-per-task",
    metavar="PATH",
    type=int,
    nargs=1,
    required=True,
    help="The number of repositories each task should handle.",
)
parser.add_argument(
    "--num-repos-to-update",
    metavar="PATH",
    type=int,
    nargs=1,
    required=True,
    help="The number of repositories to have this content added to.",
)

args = parser.parse_args()


if __name__ == "__main__":
    task_args = (args.repos_per_task[0], args.num_repos_to_update[0])
    dispatch(promote_content, args=task_args)
