"""
Sigstore-related exceptions.
"""

class SigstoreException(Exception):
    """Base class for Sigstore related Exceptions."""


class KeycloakException(SigstoreException):
    """Exception raised when an issue occurred with the current Keycloak instance."""


class MissingIdentityToken(SigstoreException):
    """Exception raised during Sigstore signing when an OIDC identity token could not be found"""


class MissingSigstoreVerificationMaterialsException(SigstoreException):
    """Exception for missing Sigstore signature verification materials."""


class VerificationFailureException(SigstoreException):
    """Exception raised when Sigstore failed to validate an artifact signature."""
