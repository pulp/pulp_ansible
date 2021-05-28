import argparse
import asyncio
import os
import textwrap

from pypi_tools import get_package_from_pypi

from git import Repo

helper = textwrap.dedent(
    """\
        Create a new tag and build a Python package.

        Example:

            $ python .ci/scripts/create_tag_and_build_package.py 3.2.5 a96ba79cfbaae2f344c86a3641a

        If the specified tag does not exist, a new tag is created in the repository.

        If the tag already exists, this script checks if the package with such a version string
        already exists on PyPI. If a package exists, the package is simply downloaded from PyPI
        and saved as pulp-ansible-.tar.gz and pulp_ansible-[tag]-py3-none-any.whl in the
        'dist' directory.

        If the package does not exist on PyPI, two new packages are built with the names
        pulp-ansible-[tag].tar.gz and pulp_ansible-[tag]-py3-none-any.whl. They are
        stored in the 'dist' directory.
    """
)
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=helper)
parser.add_argument(
    "desired_tag",
    type=str,
    help="The tag that should be created.",
)
parser.add_argument(
    "commit_sha",
    type=str,
    help="The commit that should be used for the tag.",
)
args = parser.parse_args()
desired_tag = args.desired_tag
commit_sha = args.commit_sha

release_path = os.path.dirname(os.path.abspath(__file__))
plugin_path = release_path.split("/.github")[0]

repo = Repo(plugin_path)

# Remove auth header config
with repo.config_writer() as conf:
    conf.remove_section('http "https://github.com/"')
    conf.release()

# Determine if a tag exists and if it matches the specified commit sha
tag = None
for existing_tag in repo.tags:
    if existing_tag.name == desired_tag:
        if existing_tag.commit.hexsha == commit_sha:
            tag = existing_tag
        else:
            raise RuntimeError(
                "The '{desired_tag}' tag already exists, but the commit sha does not match "
                "'{commit_sha}'."
            )

# Create a tag if one does not exist
if not tag:
    tag = repo.create_tag(desired_tag, ref=commit_sha)

# Checkout the desired tag and reset the tree
repo.head.reference = tag.commit
repo.head.reset(index=True, working_tree=True)

# Check if Package is available on PyPI
loop = asyncio.get_event_loop()
package_found = asyncio.run(get_package_from_pypi("pulp-ansible=={tag.name}", plugin_path))

if not package_found:
    os.system("python3 setup.py sdist bdist_wheel --python-tag py3")
