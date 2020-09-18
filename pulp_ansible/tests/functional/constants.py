from urllib.parse import urljoin

from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)

AH_AUTH_URL = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"

GALAXY_ANSIBLE_BASE_URL = "https://galaxy.ansible.com"

ANSIBLE_ROLE_NAME = "ansible.role"

ANSIBLE_ROLE_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, "ansible/roles/")

ANSIBLE_COLLECTION_VERSION_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, "ansible/collection_versions/")

ANSIBLE_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "ansible/ansible/")

ANSIBLE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "ansible/role/")

ANSIBLE_REPO_PATH = urljoin(BASE_REPO_PATH, "ansible/ansible/")

ANSIBLE_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, "ansible/ansible/")

ANSIBLE_GALAXY_URL = urljoin(GALAXY_ANSIBLE_BASE_URL, "api/v1/roles/")

NAMESPACE_ANSIBLE = "?namespace__name=ansible"

NAMESPACE_ELASTIC = "?namespace__name=elastic"

NAMESPACE_PULP = "?namespace__name=pulp"

NAMESPACE_TESTING = "?namespace__name=testing"

ANSIBLE_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_ANSIBLE)

ANSIBLE_PULP_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_PULP)

ANSIBLE_ELASTIC_FIXTURE_URL = urljoin(ANSIBLE_GALAXY_URL, NAMESPACE_ELASTIC)

ANSIBLE_ELASTIC_ROLE_NAMESPACE_NAME = "elastic.elasticsearch"

ANSIBLE_ELASTIC_ROLE = "elastic.elasticsearch,6.6.0"

ANSIBLE_FIXTURE_COUNT = 5

ANSIBLE_FIXTURE_CONTENT_SUMMARY = {ANSIBLE_ROLE_NAME: ANSIBLE_FIXTURE_COUNT}

# FIXME: replace this with the location of one specific content unit of your choosing
ANSIBLE_URL = urljoin(ANSIBLE_FIXTURE_URL, "")

ANSIBLE_COLLECTION_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "ansible/collection/")

ANSIBLE_DEMO_COLLECTION = "testing.k8s_demo_collection"

PULP_INSTALLER_COLLECTION = "pulp.pulp_installer"

TOKEN_DEMO_COLLECTION = "ansible.posix"

ANSIBLE_COLLECTION_CONTENT_NAME = "ansible.collection_version"

ANSIBLE_COLLECTION_FIXTURE_COUNT = 1

ANSIBLE_COLLECTION_FIXTURE_SUMMARY = {
    ANSIBLE_COLLECTION_CONTENT_NAME: ANSIBLE_COLLECTION_FIXTURE_COUNT
}

COLLECTION_METADATA = {"name": "k8s_demo_collection", "version": "0.0.3"}
"""Metadata was extracted from
https://galaxy.ansible.com/api/v2/collections/testing/k8s_demo_collection/versions/0.0.3/"""

ANSIBLE_COLLECTION_FILE_NAME = "testing-k8s_demo_collection-0.0.3.tar.gz"

ANSIBLE_COLLECTION_UPLOAD_FIXTURE_URL = urljoin(
    GALAXY_ANSIBLE_BASE_URL, f"download/{ANSIBLE_COLLECTION_FILE_NAME}"
)

ANSIBLE_COLLECTION_REQUIREMENT = """
---
collections:
- name: testing.ansible_testing_content
  version: ">=1.0.0,<=2.0.0"
  source: https://galaxy-dev.ansible.com/api/v2/collections
- testing.k8s_demo_collection
"""

TOKEN_AUTH_COLLECTIONS_URL = "https://cloud.redhat.com/api/automation-hub/v3/collections/"

TOKEN_AUTH_COLLECTION_TESTING_URL = urljoin(TOKEN_AUTH_COLLECTIONS_URL, "ansible/posix")

# Ansible Galaxy V2 Endpoints

ANSIBLE_GALAXY_COLLECTION_URL_V2 = urljoin(GALAXY_ANSIBLE_BASE_URL, "api/v2/collections/")

ANSIBLE_COLLECTION_FIXTURE_URL_V2 = urljoin(ANSIBLE_GALAXY_COLLECTION_URL_V2, "geerlingguy/k8s")

ANSIBLE_COLLECTION_TESTING_URL_V2 = urljoin(
    ANSIBLE_GALAXY_COLLECTION_URL_V2, ANSIBLE_DEMO_COLLECTION.replace(".", "/")
)

ANSIBLE_COLLECTION_PULP_URL_V2 = urljoin(
    ANSIBLE_GALAXY_COLLECTION_URL_V2, PULP_INSTALLER_COLLECTION.replace(".", "/")
)

# Ansible Galaxy V3 Endpoints

GALAXY_ANSIBLE_BASE_URL_V3 = urljoin(GALAXY_ANSIBLE_BASE_URL, "api/v3/")

ANSIBLE_GALAXY_COLLECTION_URL_V3 = urljoin(GALAXY_ANSIBLE_BASE_URL, "api/v3/collections/")

ANSIBLE_COLLECTION_FIXTURE_URL_V3 = urljoin(ANSIBLE_GALAXY_COLLECTION_URL_V3, NAMESPACE_TESTING)

ANSIBLE_COLLECTION_TESTING_URL_V3 = urljoin(
    ANSIBLE_GALAXY_COLLECTION_URL_V3, ANSIBLE_DEMO_COLLECTION.replace(".", "/")
)
