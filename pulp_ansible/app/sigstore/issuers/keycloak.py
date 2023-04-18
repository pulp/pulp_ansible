"""
Representation of Keycloak as an OIDC issuer.
"""

from sigstore.oidc import _OpenIDConfiguration
from sigstore.oidc import IdentityError

import logging
import os
import requests
import time
import urllib.parse
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
        if not urllib.parse.urlsplit(keycloak_base_url).path.startswith("/realms"):
            raise KeycloakException(
                f"Incorrect base Keycloak URL {keycloak_base_url}."
                " URL should contain the current Keycloak realm to use for authentication."
            )

        oidc_config_url = os.path.join(
            keycloak_base_url, ".well-known/openid-configuration"
        )

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

    def identity_token(self, client_id, client_secret, enable_interactive):
        """Get an identity token from Keycloak token endpoint."""
        # interactive mode is taken from the original sigstore python
        # Issuer.identity_token() implementation at
        # https://github.com/sigstore/sigstore-python/blob/v1.1.0/sigstore/oidc.py#L100
        # This method works only on browser interaction and enables out-of-bond
        # only if the former method fails.
        if enable_interactive:
            from sigstore._internal.oidc.oauth import _OAuthFlow

            code: str
            with _OAuthFlow(client_id, client_secret, self) as server:
                # Launch web browser
                if webbrowser.open(server.base_uri):
                    print("Waiting for browser interaction...")
                else:
                    server.enable_oob()
                    print(f"Go to the following link in a browser:\n\n\t{server.auth_endpoint}")

                if not server.is_oob():
                    # Wait until the redirect server populates the response
                    while server.auth_response is None:
                        time.sleep(0.1)

                    auth_error = server.auth_response.get("error")
                    if auth_error is not None:
                        raise IdentityError(f"Error response from auth endpoint: {auth_error[0]}")
                    code = server.auth_response["code"][0]
                else:
                    # In the out-of-band case, we wait until the user provides the code
                    code = input("Enter verification code: ")

            # Provide code to token endpoint
            data = {
                "grant_type": "authorization_code",
                "redirect_uri": server.redirect_uri,
                "code": code,
                "code_verifier": server.oauth_session.code_verifier,
            }
            auth = (
                client_id,
                client_secret,
            )
            logging.debug(f"PAYLOAD: data={data}")
            resp = requests.post(
                self.oidc_config.token_endpoint,
                data=data,
                auth=auth,
            )

            try:
                resp.raise_for_status()
            except requests.HTTPError as http_error:
                raise IdentityError from http_error

            token_json = resp.json()
            token_error = token_json.get("error")
            if token_error is not None:
                raise IdentityError(f"Error response from token endpoint: {token_error}")

            return str(token_json["access_token"])

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
