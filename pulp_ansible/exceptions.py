from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class CollectionNotFound(PulpException):
    def __init__(self, namespace, name, url):
        """
        :param url: The full URL that failed validation.
        :type url: str
        """
        super().__init__("PLPAN01")
        self.namespace = namespace
        self.name = name
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Collection {namespace}.{name} does not exist on {url}"
        ).format(namespace=self.namespace, name=self.name, url=self.url)
