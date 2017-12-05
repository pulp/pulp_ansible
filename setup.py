#!/usr/bin/env python3

from setuptools import setup

requirements = [
    'pulpcore-plugin',
]

setup(
    name='pulp-ansible',
    version='0.0.1a1.dev1',
    description='Pulp plugin to manage Ansible content, e.g. roles',
    author='AUTHOR',
    author_email='bbouters@redhat.com, daviddavis@redhat.com',
    url='https://github.com/bmbouter/pulp_ansible',
    install_requires=requirements,
    include_package_data=True,
    packages=['pulp_ansible', 'pulp_ansible.app'],
    entry_points={
        'pulpcore.plugin': [
            'pulp_ansible = pulp_ansible:default_app_config',
        ]
    }
)
