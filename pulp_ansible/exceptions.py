from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class CollectionNotFound(PulpException):
    error_code = "PLPAN01"

    def __init__(self, namespace, name, url):
        """
        :param url: The full URL that failed validation.
        :type url: str
        """
        # Work around a sudden api change in pulpcore 3.103.
        try:
            super().__init__()
        except BaseException:
            super().__init__(self.error_code)
        self.namespace = namespace
        self.name = name
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Collection {namespace}.{name} does not exist on {url}"
        ).format(namespace=self.namespace, name=self.name, url=self.url)
