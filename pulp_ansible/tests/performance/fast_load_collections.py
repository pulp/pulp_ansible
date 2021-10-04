import argparse
import os

import django

django.setup()

from pulpcore.plugin.tasking import (  # noqa otherwise E402: module level not at top of file
    dispatch,
)

from pulp_ansible.app.tasks.test_tasks import (  # noqa otherwise E402: module level not at top of file
    import_collection_from_path,
)


parser = argparse.ArgumentParser(description="Quickly load collections form a folder.")

parser.add_argument(
    "--collections-dir",
    metavar="PATH",
    type=str,
    nargs=1,
    required=True,
    help="The full path to a director containing collection tarballs.",
)

args = parser.parse_args()


if __name__ == "__main__":
    for root, dirs, files in os.walk(args.collections_dir[0]):
        for file in files:
            if file.endswith(".tar.gz"):
                async_result = dispatch(
                    import_collection_from_path, args=(os.path.join(root, file),)
                )
