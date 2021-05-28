import argparse
import asyncio
import os
import textwrap

from pypi_tools import get_package_from_pypi

helper = textwrap.dedent(
    """\
        Get Python client from PyPI or generate it using openapi-generator-cli.

        Example:

            $ python .ci/scripts/get_or_create_python_client.py 3.2.5

        If a client package with the specified version exists on PyPI, it is downloaded from there.

        If a client package with the specified version does not exist on PyPI, it is generated using
        openapi-generator-cli.
    """
)
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=helper)
parser.add_argument(
    "client_version",
    type=str,
    help="The version for the client package.",
)
parser.add_argument(
    "commit_sha",
    type=str,
    help="The commit that should be used for the tag.",
)
args = parser.parse_args()
client_version = args.client_version

release_path = os.path.dirname(os.path.abspath(__file__))
plugin_path = release_path.split("/.github")[0]

# Check if the client package is available on PyPI
loop = asyncio.get_event_loop()
package_found = asyncio.run(
    get_package_from_pypi("pulp-ansible-client=={client_version}", plugin_path)
)

if not package_found:
    os.system("python3 setup.py sdist bdist_wheel --python-tag py3")
