import os
import subprocess
import tempfile


def make_cv_tarball(namespace, name, version):
    """Create a collection version from scratch."""
    tdir = tempfile.mkdtemp()
    subprocess.run(f"ansible-galaxy collection init {namespace}.{name}", shell=True, cwd=tdir)
    os.makedirs(os.path.join(tdir, namespace, name, "meta"))
    with open(os.path.join(tdir, namespace, name, "meta", "runtime.yml"), "w") as f:
        f.write('requires_ansible: ">=2.13"\n')
    with open(os.path.join(tdir, namespace, name, "README.md"), "w") as f:
        f.write("# title\ncollection docs\n")
    build_pid = subprocess.run(
        "ansible-galaxy collection build .",
        shell=True,
        cwd=os.path.join(tdir, namespace, name),
        stdout=subprocess.PIPE,
    )
    tarfn = build_pid.stdout.decode("utf-8").strip().split()[-1]
    return tarfn
