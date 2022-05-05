from urllib.parse import urljoin

from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)


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
ANSIBLE_DEMO_COLLECTION_VERSION = "0.0.3"

ANSIBLE_DEMO_COLLECTION_REQUIREMENTS = f"collections:\n  - {ANSIBLE_DEMO_COLLECTION}"

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
  source: https://galaxy-dev.ansible.com/
- testing.k8s_demo_collection
- rshad.collection_demo
- brightcomputing.bcm
"""

TABLES_TO_KEEP = (
    # django's sqlclear or sqlflush excludes this table when cleaning up the db
    "django_migrations",
    # not to create an admin user every time
    "auth_user",
    "galaxy_user",
    # not to be doomed by the lack of permissions
    "auth_permission",
    "core_accesspolicy",
    "core_role",
    "core_role_permissions",
    # 'auth_permission' references it, so it should not be truncated
    "django_content_type",
    # not to freak out the tasking system
    "core_reservedresource",
    "core_reservedresourcerecord",
    "core_task",
    "core_taskgroup",
    "core_taskreservedresource",
    "core_taskreservedresourcerecord",
    "core_worker",
)

TRUNCATE_TABLES_QUERY_BASH = f"""
DO $$
  BEGIN
    EXECUTE format('TRUNCATE %s',
                    (SELECT STRING_AGG(table_name, ', ')
                       FROM information_schema.tables
                         WHERE table_schema = 'public' AND table_name NOT IN {TABLES_TO_KEEP}
                    )
                  );
  END
$$;
"""  # noqa

TEST_COLLECTION_CONFIGS = [
    {"name": "a", "namespace": "test", "dependencies": {"test.b": "*"}},
    {"name": "b", "namespace": "test", "dependencies": {"test.c": "*"}},
    {"name": "c", "namespace": "test", "dependencies": {"test.d": "*"}},
    {"name": "d", "namespace": "test"},
    {"name": "e", "namespace": "test", "dependencies": {"test.f": "*", "test.g": "*"}},
    {"name": "f", "namespace": "test", "dependencies": {"test.h": "<=3.0.0"}},
    {"name": "g", "namespace": "test", "dependencies": {"test.d": "*"}},
    {"name": "h", "namespace": "test", "version": "1.0.0"},
    {"name": "h", "namespace": "test", "version": "2.0.0"},
    {"name": "h", "namespace": "test", "version": "3.0.0"},
    {"name": "h", "namespace": "test", "version": "4.0.0"},
    {"name": "h", "namespace": "test", "version": "5.0.0"},
]
