#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("requirements.txt") as requirements:
    requirements = requirements.readlines()

with open("README.rst") as f:
    long_description = f.read()

setup(
    name="pulp-ansible",
    version="0.23.1",
    description="Pulp plugin to manage Ansible content, e.g. roles",
    long_description=long_description,
    license="GPLv2+",
    author="Pulp Ansible Plugin Project Developers",
    author_email="pulp-dev@redhat.com",
    url="https://github.com/pulp/pulp_ansible",
    python_requires=">=3.9",
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=["tests"]),
    classifiers=(
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
    ),
    entry_points={
        "pulpcore.plugin": ["pulp_ansible = pulp_ansible:default_app_config"],
        "pytest11": ["pulp_ansible = pulp_ansible.pytest_plugin"],
    },
)
