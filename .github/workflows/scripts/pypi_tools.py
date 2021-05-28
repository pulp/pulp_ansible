import os
import shutil

from bandersnatch.mirror import BandersnatchMirror
from bandersnatch.master import Master
from bandersnatch.configuration import BandersnatchConfig
from packaging.requirements import Requirement


# Check if Package is available on PyPI
async def get_package_from_pypi(package_name, plugin_path):
    """
    Download a package from PyPI.

    :param name: name of the package to download from PyPI
    :return: String path to the package
    """
    config = BandersnatchConfig().config
    config["mirror"]["master"] = "https://pypi.org"
    config["mirror"]["workers"] = "1"
    config["mirror"]["directory"] = plugin_path
    if not config.has_section("plugins"):
        config.add_section("plugins")
    config["plugins"]["enabled"] = "blocklist_release\n"
    if not config.has_section("allowlist"):
        config.add_section("allowlist")
    config["plugins"]["enabled"] += "allowlist_release\nallowlist_project\n"
    config["allowlist"]["packages"] = "\n".join([package_name])
    os.mkdir(os.path.join(plugin_path, "dist"))
    async with Master("https://pypi.org/") as master:
        mirror = BandersnatchMirror(homedir=plugin_path, master=master)
        name = Requirement(package_name).name
        result = await mirror.synchronize([name])
    package_found = False

    for package in result[name]:
        current_path = os.path.join(plugin_path, package)
        destination_path = os.path.join(plugin_path, "dist", os.path.basename(package))
        shutil.move(current_path, destination_path)
        package_found = True
    return package_found
