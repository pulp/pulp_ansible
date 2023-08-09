"""
An OIDC issuer implementation for automated signing flows
(OIDC Client Credentials Flow) that enables retrieving an identity
token without user interaction.
"""

from sigstore.errors import NetworkError
from sigstore.oidc import _OpenIDConfiguration
from sigstore.oidc import (
    IdentityError,
    IdentityToken,
    IssuerError,
)

import logging
import os
import requests

from pulp_ansible.app.sigstore.issuers.base import BaseIssuer


log = logging.getLogger(__name__)


class _CustomOpenIDConfiguration(_OpenIDConfiguration):
    """
    Extends sigstore-python's _OpenIDConfiguration
    with checks relative to custom issuers configuration.
    """


class NonInteractiveIssuer(BaseIssuer):
    """
    Custom representation of an OIDC Issuer for automated signing flows.
    Extends the functionalities provided by
    https://github.com/sigstore/sigstore-python/blob/v2.0.0rc2/sigstore/oidc.py#L245
    """

    def __init__(self, issuer_base_url):
        """Create a new issuer instance with custom endpoints."""
        oidc_config_url = os.path.join(issuer_base_url, ".well-known/openid-configuration")

        resp: requests.Response = requests.get(oidc_config_url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as http_error:
            log.error(http_error.response)
            raise IssuerError from http_error

        try:
            self.oidc_config = _CustomOpenIDConfiguration.parse_obj(resp.json())
        except ValueError as exc:
            raise IssuerError(f"Identity provider returned invalid configuration: {exc}")

    def identity_token(self, client_id, client_secret):
        """Get an identity token from a token endpoint."""
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid",
            "grant_type": "client_credentials",
        }

        try:
            resp = requests.post(
                self.oidc_config.token_endpoint,
                data=data,
            )

        except (requests.ConnectionError, requests.Timeout) as exc:
            raise NetworkError from exc

        try:
            resp.raise_for_status()
        except requests.HTTPError as http_error:
            raise IdentityError(
                f"Token request failed with {resp.status_code}"
            ) from http_error

        token_json = resp.json()
        token_error = token_json.get("error")
        if token_error is not None:
            raise IdentityError(f"Error response from token endpoint: {resp_error}")

        return IdentityToken(token_json["access_token"])
