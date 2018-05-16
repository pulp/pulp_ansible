#!/usr/bin/env python3

from setuptools import setup

requirements = [
    'pulpcore-plugin',
]

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='pulp-ansible',
    version='0.1.0b2',
    description='Pulp plugin to manage Ansible content, e.g. roles',
    long_description=long_description,
    author='Pulp Ansible Plugin Project Developers',
    author_email='pulp-dev@redhat.com',
    url='https://github.com/pulp/pulp_ansible',
    install_requires=requirements,
    include_package_data=True,
    packages=['pulp_ansible', 'pulp_ansible.app'],
    classifiers=(
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ),
    entry_points={
        'pulpcore.plugin': [
            'pulp_ansible = pulp_ansible:default_app_config',
        ]
    }
)
