#!/usr/bin/env python3

from setuptools import setup

requirements = [
    'pulpcore-plugin',
]

setup(
    name='pulp-plugin-template',
    version='0.0.1a1.dev1',
    description='pulp-plugin-template plugin for the Pulp Project',
    author='AUTHOR',
    author_email='author@email.here',
    url='http://example.com/',
    install_requires=requirements,
    include_package_data=True,
    packages=['pulp_plugin_template', 'pulp_plugin_template.app'],
    entry_points={
        'pulpcore.plugin': [
            'pulp_plugin_template = pulp_plugin_template:default_app_config',
        ]
    }
)
