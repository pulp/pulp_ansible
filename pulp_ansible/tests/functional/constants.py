from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL  # noqa:F401
from pulp_smash.pulp3.constants import (  # noqa:F401
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)

DOWNLOAD_POLICIES = ['immediate', 'on_demand', 'streamed']
"""Allowed download policies for this plugin."""

ANSIBLE_ROLE_NAME = 'ansible.role'

ANSIBLE_ROLE_CONTENT_PATH = urljoin(CONTENT_PATH, 'ansible/roles/')

ANSIBLE_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, 'ansible/ansible')

ANSIBLE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'ansible/ansible/')

ANSIBLE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'ansible/ansible/')


ANSIBLE_GALAXY_URL = 'https://galaxy.ansible.com/api/v1/roles/'

NAMESPACE_ANSIBLE = '?namespace__name=ansible'
NAMESPACE_PULP = '?namespace__name=pulp'

ANSIBLE_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_ANSIBLE)
ANSIBLE_PULP_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_PULP)

ANSIBLE_FIXTURE_CONTENT_SUMMARY = {
    ANSIBLE_ROLE_NAME: 5,
}
ANSIBLE_FIXTURE_COUNT = 5

# FIXME: replace this with the location of one specific content unit of your choosing
ANSIBLE_URL = urljoin(ANSIBLE_FIXTURE_URL, '')
