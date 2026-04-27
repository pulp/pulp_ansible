from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class CollectionNotFound(PulpException):
    error_code = "ANS0001"

    def __init__(self, namespace, name, url):
        self.namespace = namespace
        self.name = name
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Collection {namespace}.{name} does not exist on {url}"
        ).format(namespace=self.namespace, name=self.name, url=self.url)


class RemoteURLRequiredError(PulpException):
    """
    Raised when a remote is missing a required URL for synchronization.
    """

    error_code = "ANS0002"

    def __str__(self):
        return f"[{self.error_code}] " + _("A remote must have a url specified to synchronize.")


class CollectionFilenameParseError(PulpException):
    """
    Raised when unable to parse a collection filename.
    """

    error_code = "ANS0003"

    def __init__(self, filename):
        """
        :param filename: The filename that failed to parse
        :type filename: str
        """
        self.filename = filename

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Failed to parse Collection file upload '{filename}'"
        ).format(filename=self.filename)


class InvalidCollectionFilenameError(PulpException):
    """
    Raised when collection filename format is invalid.
    """

    error_code = "ANS0004"

    def __init__(self, filename):
        """
        :param filename: The invalid filename
        :type filename: str
        """
        self.filename = filename

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Invalid filename {filename}. Expected format: namespace-name-version.tar.gz"
        ).format(filename=self.filename)


class InvalidCollectionVersionError(PulpException):
    """
    Raised when collection version string is invalid.
    """

    error_code = "ANS0005"

    def __init__(self, version, filename):
        """
        :param version: The invalid version string
        :type version: str
        :param filename: The filename containing the version
        :type filename: str
        """
        self.version = version
        self.filename = filename

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Invalid version string {version} from filename {filename}. "
            "Expected semantic version format."
        ).format(version=self.version, filename=self.filename)


class CollectionFieldTooLongError(PulpException):
    """
    Raised when a collection field exceeds maximum length.
    """

    error_code = "ANS0006"

    def __init__(self, field_name, max_length):
        """
        :param field_name: Name of the field that's too long
        :type field_name: str
        :param max_length: Maximum allowed length
        :type max_length: int
        """
        self.field_name = field_name
        self.max_length = max_length

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Expected {field_name} to be max length of {max_length}"
        ).format(field_name=self.field_name, max_length=self.max_length)


class APIVersionNotFoundError(PulpException):
    """
    Raised when API version cannot be determined from URL.
    """

    error_code = "ANS0007"

    def __init__(self, url):
        """
        :param url: The URL where version couldn't be found
        :type url: str
        """
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _("Could not determine API version for: {url}").format(
            url=self.url
        )


class AvailableVersionsNotFoundError(PulpException):
    """
    Raised when 'available_versions' field is missing from API response.
    """

    error_code = "ANS0008"

    def __init__(self, url):
        """
        :param url: The URL where available_versions wasn't found
        :type url: str
        """
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _("Could not find 'available_versions' at {url}").format(
            url=self.url
        )


class UnsupportedAPIVersionError(PulpException):
    """
    Raised when API only supports unsupported versions.
    """

    error_code = "ANS0009"

    def __init__(self, url):
        """
        :param url: The URL with unsupported API versions
        :type url: str
        """
        self.url = url

    def __str__(self):
        return f"[{self.error_code}] " + _("Unsupported API versions at {url}").format(url=self.url)


class RequirementsFileParseError(PulpException):
    """
    Raised when unable to parse requirements file YAML.
    """

    error_code = "ANS0010"

    def __init__(self, filename, error):
        """
        :param filename: The requirements filename
        :type filename: str
        :param error: The parsing error details
        :type error: str
        """
        self.filename = filename
        self.error = error

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Failed to parse the collection requirements yml: {file} with error {error}"
        ).format(file=self.filename, error=self.error)


class InvalidRequirementsFormatError(PulpException):
    """
    Raised when requirements file has invalid format or structure.
    """

    error_code = "ANS0011"

    def __init__(self, message):
        """
        :param message: Description of the format error
        :type message: str
        """
        self.message = message

    def __str__(self):
        return f"[{self.error_code}] " + self.message


class CollectionNameRequiredError(PulpException):
    """
    Raised when collection name is missing from requirements entry.
    """

    error_code = "ANS0012"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Collections requirement entry should contain the key name."
        )


class InvalidCollectionNameFormatError(PulpException):
    """
    Raised when collection name doesn't follow namespace.name format.
    """

    error_code = "ANS0013"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Collections requirement entry should contain the collection name in the "
            "format <namespace>.<name>."
        )


class MissingExpectedFieldsError(PulpException):
    """
    Raised when expected_namespace, expected_name, expected_version are missing.
    """

    error_code = "ANS0014"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "expected_namespace, expected_name, and expected_version must be "
            "specified when using artifact or upload objects"
        )


class SignatureVerificationError(PulpException):
    """
    Raised when signature verification fails.
    """

    error_code = "ANS0015"

    def __init__(self, message):
        """
        :param message: Description of the verification failure
        :type message: str
        """
        self.message = message

    def __str__(self):
        return f"[{self.error_code}] " + _("Signature verification failed: {message}").format(
            message=self.message
        )


class UnsupportedStorageBackendError(PulpException):
    """
    Raised when the domain's storage class is not supported for generating download URLs.
    """

    error_code = "ANS0016"

    def __init__(self, storage_class):
        self.storage_class = storage_class

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "The storage backend '{storage_class}' is not supported"
        ).format(storage_class=self.storage_class)


class CollectionFileNotFoundError(PulpException):
    """
    Raised when a required file is not found inside a collection tarball.
    """

    error_code = "ANS0017"

    def __init__(self, file_path):
        self.file_path = file_path

    def __str__(self):
        return f"[{self.error_code}] " + _("{file_path} not found").format(file_path=self.file_path)
