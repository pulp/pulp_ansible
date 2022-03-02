import socket

from dynaconf import settings

LOGGING = {
    "loggers": {
        "pulp_ansible.app.tasks.collection.import_collection": {
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

ANSIBLE_API_HOSTNAME = "https://" + socket.getfqdn()
ANSIBLE_CONTENT_HOSTNAME = settings.CONTENT_ORIGIN + "/pulp/content"
ANSIBLE_SIGNING_TASK_LIMITER = 10
ANSIBLE_CERTS_DIR = "/etc/pulp/certs/"
ANSIBLE_DEFAULT_DISTRIBUTION_PATH = None
ANSIBLE_URL_NAMESPACE = ""
