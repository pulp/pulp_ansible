"""
Base class for representing Sigstore OIDC issuers.
"""


class BaseIssuer:
    """Representation of a base OIDC issuer."""

    def __init__(self, *args, **kwargs):
        """Override the constructor to perform issuer configuration validation."""
        raise NotImplementedError

    def identity_token(self, *args, **kwargs):
        """Get an identity token from the Issuer."""
        raise NotImplementedError
