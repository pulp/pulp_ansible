from urllib.parse import urljoin

from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_REPO_PATH,
)


GALAXY_ANSIBLE_BASE_URL = "https://galaxy.ansible.com"

ANSIBLE_ROLE_NAME = "ansible.role"

ANSIBLE_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "ansible/ansible/")

ANSIBLE_REPO_PATH = urljoin(BASE_REPO_PATH, "ansible/ansible/")

ANSIBLE_GALAXY_URL = urljoin(GALAXY_ANSIBLE_BASE_URL, "api/v1/roles/")

NAMESPACE_ANSIBLE = "?owner__username=ansible"

NAMESPACE_ELASTIC = "?owner__username=elastic"

NAMESPACE_PULP = "?owner__username=pulp"

NAMESPACE_TESTING = "?owner__username=testing"

ANSIBLE_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_ANSIBLE)

ANSIBLE_ELASTIC_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_ELASTIC)

ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME = "elastic.elasticsearch"

ANSIBLE_ELASTIC_ROLE = "elastic.elasticsearch,6.6.0"

ANSIBLE_FIXTURE_COUNT = 5

ANSIBLE_FIXTURE_CONTENT_SUMMARY = {ANSIBLE_ROLE_NAME: ANSIBLE_FIXTURE_COUNT}

ANSIBLE_DEMO_COLLECTION = "testing.k8s_demo_collection"
ANSIBLE_DEMO_COLLECTION_VERSION = "0.0.3"

ANSIBLE_DEMO_COLLECTION_REQUIREMENTS = f"collections:\n  - {ANSIBLE_DEMO_COLLECTION}"

COLLECTION_METADATA = {"name": "k8s_demo_collection", "version": "0.0.3"}
"""Metadata was extracted from
https://galaxy.ansible.com/api/v2/collections/testing/k8s_demo_collection/versions/0.0.3/"""

ANSIBLE_COLLECTION_FILE_NAME = "testing-k8s_demo_collection-0.0.3.tar.gz"

ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL = urljoin(
    GALAXY_ANSIBLE_BASE_URL, f"download/{ANSIBLE_COLLECTION_FILE_NAME}"
)
