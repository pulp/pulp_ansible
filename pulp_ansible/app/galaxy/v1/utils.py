import datetime
import glob
import os
import subprocess
import tempfile
import yaml


def get_path_git_root(path):
    """
    Find the root directory of a git checkout.
    """
    cmd = "git rev-parse --show-toplevel"
    pid = subprocess.run(cmd, cwd=path, shell=True, stdout=subprocess.PIPE)
    return pid.stdout.decode("utf-8").strip()


def get_path_head_date(path):
    """
    Get the timestamp for the most recent commit.
    """
    cmd = 'git log -1 --format="%ci"'
    pid = subprocess.run(cmd, cwd=path, shell=True, stdout=subprocess.PIPE)
    ds = pid.stdout.decode("utf-8").strip()

    # 2021-10-31 00:03:43 -0500
    ts = datetime.datetime.strptime(ds, "%Y-%m-%d %H:%M:%S %z")
    return ts


def get_path_role_repository(path):
    """
    Get the remote origin url.
    """
    cmd = "git remote -v | head -1 | awk '{print $2}'"
    pid = subprocess.run(cmd, cwd=path, shell=True, stdout=subprocess.PIPE)
    origin = pid.stdout.decode("utf-8").strip()
    return origin


def get_path_role_meta(path):
    """
    Get the parsed role metadata.
    """
    metaf = os.path.join(path, "meta", "main.yml")
    with open(metaf, "r") as f:
        meta = yaml.load(f.read())
    return meta


def get_path_role_name(path):
    """
    Enumerate a role name from a role checkout using heuristics.
    """
    name = get_path_galaxy_key(path, "name")
    if name is not None:
        return name

    metaf = os.path.join(path, "meta", "main.yml")
    meta = None
    if os.path.exists(metaf):
        with open(metaf, "r") as f:
            meta = yaml.load(f.read())

    if meta and "role_name" in meta["galaxy_info"]:
        name = meta["galaxy_info"]["role_name"]
    else:
        cmd = "git remote -v | head -1 | awk '{print $2}'"
        pid = subprocess.run(cmd, cwd=path, shell=True, stdout=subprocess.PIPE)
        origin = pid.stdout.decode("utf-8").strip()
        name = origin.replace("https://github.com/", "").split("/")[1]

        if "ansible-role-" in name:
            name = name.replace("ansible-role-", "")
        if name.startswith("ansible-"):
            name = name.replace("ansible-", "")
        if name.endswith("-ansible"):
            name = name.replace("-ansible", "")
        if name.startswith("ansible."):
            name = name.replace("ansible.", "")

    # https://github.com/angstwad/docker.ubuntu -> docker_ubuntu
    if "." in name:
        name = name.replace(".", "_")

    #  https://github.com/sbaerlocher/ansible.update-management -> update_management
    if "-" in name:
        name = name.replace("-", "_")

    return name


def get_path_role_namespace(path):
    """
    Enumerate the github_user/namespace for a role checkout.
    """
    namespace = get_path_galaxy_key(path, "namespace")
    if namespace is not None:
        return namespace

    cmd = "git remote -v | head -1 | awk '{print $2}'"
    pid = subprocess.run(cmd, cwd=path, shell=True, stdout=subprocess.PIPE)
    origin = pid.stdout.decode("utf-8").strip()
    namespace = origin.replace("https://github.com/", "").split("/")[0]

    if namespace == "ansible-collections":
        namespace = "ansible"

    return namespace


def get_path_role_version(path):
    """
    Enumerate a version for a role checkout using heuristics.
    """
    # try the metdata first
    version = get_path_galaxy_key(path, "version")
    if version is not None:
        return version
    # generate one from the commit timestamp
    ds = get_path_head_date(path)
    parts = ds.isoformat().split("T")
    ymd = parts[0].split("-")
    ts = parts[1].replace(":", "")
    ts = ts.replace("-", "")
    ts = ts.replace("+", "")
    version = "1.0.0" + "+" + ymd[0] + ymd[1] + ymd[2] + ts

    return version


def path_is_role(path):
    """
    Check if a directory looks like a legacy role.
    """
    namespace = get_path_galaxy_key(path, "namespace")
    name = get_path_galaxy_key(path, "name")
    if namespace is not None and name is not None:
        return False

    paths = glob.glob(f"{path}/*")
    paths = [os.path.basename(x) for x in paths]

    if "plugins" in paths:
        return False

    if "tasks" in paths:
        return True

    if "library" in paths:
        return True

    if "handlers" in paths:
        return True

    if "defaults" in paths:
        return True

    return False


def make_runtime_yaml(path):
    """
    Place a runtime.yml file in a checkout if it doesn't exist.
    """
    metadir = os.path.join(path, "meta")
    runtimef = os.path.join(metadir, "runtime.yml")

    if not os.path.exists(metadir):
        os.makedirs(metadir)

    data = {"requires_ansible": ">=2.10"}

    with open(runtimef, "w") as f:
        yaml.dump(data, f)


def get_path_galaxy_key(path, key):
    """
    Get a desired key from a galaxy.yml.
    """
    gfn = os.path.join(path, "galaxy.yml")
    if not os.path.exists(gfn):
        return None
    with open(gfn, "r") as f:
        ds = yaml.load(f.read())
    return ds.get(key)


def set_path_galaxy_key(path, key, value):
    """
    Write a key and value into a galaxy.yml.
    """
    gfn = os.path.join(path, "galaxy.yml")
    with open(gfn, "r") as f:
        ds = yaml.load(f.read())
    ds[key] = value
    with open(gfn, "w") as f:
        yaml.dump(ds, f)


def set_path_galaxy_version(path, version):
    """
    Set the collection version in galaxy.yml.
    """
    set_path_galaxy_key(path, "version", version)


def set_path_galaxy_repository(path, repository):
    """
    Set the repository url in a galaxy.yml.
    """
    set_path_galaxy_key(path, "repository", repository)


def get_role_version(
    checkout_path=None,
    github_user=None,
    github_repo=None,
    github_reference=None,
    alternate_role_name=None,
):
    """
    Enumerate a legacy role version using heuristics.
    """
    if checkout_path is None:
        clone_url = f"https://github.com/{github_user}/{github_repo}"
        checkout_path = tempfile.mkdtemp()
        cmd = f"git clone {clone_url} {checkout_path}"
        pid = subprocess.run(cmd, shell=True)

    # update the tags
    pid = subprocess.run("git fetch --tags", shell=True, cwd=checkout_path, stdout=subprocess.PIPE)
    assert pid.returncode == 0, "fetching tags failed"
    # list the tags
    pid = subprocess.run("git tag -l", shell=True, cwd=checkout_path, stdout=subprocess.PIPE)
    assert pid.returncode == 0, "listing tags failed"
    # clean up the tag list
    tags = pid.stdout.decode("utf-8")
    tags = tags.split("\n")
    tags = [x.strip() for x in tags if x.strip()]
    # return the expected github reference aka "version" if it is a current tag
    if github_reference and github_reference in tags:
        return github_reference
    # return the latest tag
    if tags:
        return tags[-1]
    # fallback to using a synthetic version based on latest commit timestamp
    return get_path_role_version(checkout_path)


def get_tag_commit_hash(git_url, tag, checkout_path=None):
    """
    Get the commit hash for a specific tag.
    """
    if checkout_path is None:
        checkout_path = tempfile.mkdtemp()
        pid = subprocess.run(f"git clone {git_url} {checkout_path}", shell=True)
    pid = subprocess.run(
        "git log -1 --format='%H'", shell=True, cwd=checkout_path, stdout=subprocess.PIPE
    )
    commit_hash = pid.stdout.decode("utf-8").strip()
    return commit_hash


def get_tag_commit_date(git_url, tag, checkout_path=None):
    """
    Get the ISO formatted commit timestamp of a specific tag.
    """
    if checkout_path is None:
        checkout_path = tempfile.mkdtemp()
        pid = subprocess.run(f"git clone {git_url} {checkout_path}", shell=True)
    pid = subprocess.run(
        "git log -1 --format='%ci'", shell=True, cwd=checkout_path, stdout=subprocess.PIPE
    )
    commit_date = pid.stdout.decode("utf-8").strip()

    # 2022-06-07 22:18:41 +0000 --> 2022-06-07T22:18:41
    parts = commit_date.split()
    return f"{parts[0]}T{parts[1]}"
