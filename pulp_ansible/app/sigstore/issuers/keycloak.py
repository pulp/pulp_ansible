"""
Representation of Keycloak as an OIDC issuer.
"""

from sigstore.oidc import _OpenIDConfiguration
from sigstore.oidc import IdentityError

import logging
import os
import requests
import time
import webbrowser

from pulp_ansible.app.sigstore.exceptions import KeycloakException
from pulp_ansible.app.sigstore.issuers.base import BaseIssuer


log = logging.getLogger(__name__)


class _KeycloakOpenIDConfiguration(_OpenIDConfiguration):
    """
    Extends sigstore-python's _OpenIDConfiguration
    with checks relative to Keycloak configuration.
    """


class Keycloak(BaseIssuer):
    """
    Custom representation of Keycloak as an OIDC Issuer.
    Extends the functionalities provided by
    https://github.com/sigstore/sigstore-python/blob/v1.1.0/sigstore/oidc.py#L55
    """

    def __init__(self, keycloak_base_url):
        """Create a new Keycloak issuer with custom endpoints."""
        oidc_config_url = os.path.join(keycloak_base_url, ".well-known/openid-configuration")

        resp: requests.Response = requests.get(oidc_config_url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as http_error:
            log.error(http_error.response)
            raise KeycloakException from http_error

        try:
            self.oidc_config = _KeycloakOpenIDConfiguration.parse_obj(resp.json())
        except ValueError as exc:
            raise KeycloakException(f"Keycloak returned invalid configuration: {exc}")

    def identity_token(self, client_id, client_secret):
        """Get an identity token from Keycloak token endpoint."""
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid",
            "grant_type": "client_credentials",
        }

        resp = requests.post(
            self.oidc_config.token_endpoint,
            data=data,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as http_error:
            raise IdentityError from http_error

        resp_json = resp.json()
        resp_error = resp_json.get("error")
        if resp_error is not None:
            raise IdentityError(f"Error response from token endpoint: {resp_error}")

        return str(resp_json["id_token"])
