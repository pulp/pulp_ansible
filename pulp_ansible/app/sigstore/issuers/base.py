"""
Base class for representing Sigstore OIDC issuers.
"""

from sigstore.oidc import _OpenIDConfiguration
from sigstore.oidc import IdentityError

import logging
import requests
import time
import urllib.parse
import webbrowser

log = logging.getLogger(__name__)


class BaseIssuer:
    """Representation of a base OIDC issuer."""
    def __init__(self, *args, **kwargs):
        """Override the constructor to perform issuer configuration validation."""
        raise NotImplementedError

    def identity_token(self, *args, **kwargs):
        """Get an identity token from the Issuer."""
        raise NotImplementedError
        