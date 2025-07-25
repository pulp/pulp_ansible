import socket

LOGGING = {
    "loggers": {
        "pulp_ansible.app.tasks.upload.process_collection_artifact": {
            "level": "INFO",
            "handlers": ["collection_import"],
            "propagate": False,
        }
    },
    "handlers": {
        "collection_import": {
            "level": "DEBUG",
            "class": "pulp_ansible.app.logutils.CollectionImportHandler",
            "formatter": "simple",
        }
    },
    "dynaconf_merge": True,
}

DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_ansible.app.global_access_conditions"],
}

ANSIBLE_API_HOSTNAME = "https://" + socket.getfqdn()
ANSIBLE_CONTENT_HOSTNAME = "@format {this.CONTENT_ORIGIN}/pulp/content"
ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION = True
ANSIBLE_SIGNING_TASK_LIMITER = 10
ANSIBLE_DEFAULT_DISTRIBUTION_PATH = None
ANSIBLE_URL_NAMESPACE = ""
ANSIBLE_COLLECT_DOWNLOAD_LOG = False
ANSIBLE_COLLECT_DOWNLOAD_COUNT = False
# Assign existing value taken from the main pulpcore settings.
ANSIBLE_AUTHENTICATION_CLASSES = "@get REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES"
ANSIBLE_PERMISSION_CLASSES = "@get REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES"

GALAXY_API_ROOT = "pulp_ansible/galaxy/<path:path>/api/"
