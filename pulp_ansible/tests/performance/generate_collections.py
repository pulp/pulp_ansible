import argparse

import django

django.setup()

from pulpcore.plugin.tasking import (  # noqa otherwise E402: module level not at top of file
    dispatch,
)

from pulp_ansible.app.tasks.test_tasks import (  # noqa otherwise E402: module level not at top of file
    create_namespace,
)


parser = argparse.ArgumentParser(description="Generate some collections.")

parser.add_argument(
    "--num-namespaces",
    metavar="N",
    type=int,
    nargs=1,
    required=True,
    help="The number of namespaces to generate.",
)
parser.add_argument(
    "--collections-per-namespace",
    metavar="N",
    type=int,
    nargs=1,
    required=True,
    help="The number of collections per namespace",
)
parser.add_argument(
    "--versions-per-collection",
    metavar="N",
    type=int,
    nargs=1,
    required=True,
    help="The number of versions per collection",
)
parser.add_argument(
    "--base-path",
    metavar="PATH",
    type=str,
    nargs=1,
    required=True,
    help="The full path where collections should be written",
)

args = parser.parse_args()


if __name__ == "__main__":
    for namespace_i in range(args.num_namespaces[0]):
        kwargs = {
            "collection_n": args.collections_per_namespace[0],
            "versions_per_collection": args.versions_per_collection[0],
        }
        async_result = dispatch(create_namespace, args=(args.base_path[0],), kwargs=kwargs)
