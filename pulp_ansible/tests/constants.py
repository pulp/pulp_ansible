from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL  # noqa:F401
from pulp_smash.pulp3.constants import (  # noqa:F401
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)

ANSIBLE_FIXTURE_URL = 'https://galaxy.ansible.com/api/v1/roles/?namespace=ansible'
ANSIBLE2_FIXTURE_URL = 'https://galaxy.ansible.com/api/v1/roles/?namespace=pulp'
ANSIBLE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'ansible/')
