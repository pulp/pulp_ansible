from django.core.management import BaseCommand, CommandError
from django.db.utils import IntegrityError

import argparse
import json
import os

from gettext import gettext as _
from pathlib import Path
from voluptuous import Optional, Required, Schema

from pulp_ansible.app.models import SigstoreSigningService


SIGSTORE_CONFIGURATION_FILE_SCHEMA = Schema(
    {
        Required("name"): str,
        Optional("rekor-url"): str,
        Optional("tuf-url"): str,
        Optional("rekor-root-pubkey"): str,
        Optional("fulcio-url"): str,
        Optional("oidc-issuer"): str,
        Optional("ctfe-pubkey"): str,
        Optional("credentials-file-path"): str,
        Optional("enable-interactive"): bool,
    }
)

# Taken from https://github.com/sigstore/sigstore-python/blob/55f98f663721be34a5e5b63fb72e740c3d580f66/sigstore/_cli.py#L64
def _to_bool(val):
    if isinstance(val, bool):
        return val
    val = val.lower()
    if val in {"y", "yes", "true", "t", "on", "1"}:
        return True
    elif val in {"n", "no", "false", "f", "off", "0"}:
        return False
    else:
        raise ValueError(f"can't coerce '{val}' to a boolean")


class Command(BaseCommand):
    """
    Django management command for adding a Sigstore signing service.
    This command is in tech preview.
    """

    help = "Adds a new Sigstore signing service. [tech-preview]"

    def add_arguments(self, parser):
        sign_options = parser.add_argument_group("Sign options")
        sign_options.add_argument(
            "--from-file",
            help=_("Load the Sigstore configuration from a JSON file. File configuration can be overriden by specified arguments.\n"),
        )
        sign_options.add_argument(
            "--name",
            type=str,
            metavar="NAME",
            help=_("Name for registering the Sigstore signing service.\n"),
        )
        sign_options.add_argument(
            "--rekor-url",
            metavar="URL",
            type=str,
            default="https://rekor.sigstore.dev",
            help=_("The Rekor instance to use. WARNING: defaults to the public good Sigstore instance https://rekor.sigstore.dev"),
        )
        sign_options.add_argument(
            "--tuf-url",
            metavar="URL",
            type=str,
            default="https://sigstore-tuf-root.storage.googleapis.com/",
            help=_("The TUF repository to use. WARNING: defaults to the public TUF metadata repository https://sigstore-tuf-root.storage.googleapis.com/"),
        )
        sign_options.add_argument(
            "--rekor-root-pubkey",
            metavar="FILE",
            type=argparse.FileType("rb"),
            help=_("A PEM-encoded root public key for Rekor itself"),
            default=None,
        )
        sign_options.add_argument(
            "--fulcio-url",
            metavar="URL",
            type=str,
            default="https://fulcio.sigstore.dev",
            help=_("The Fulcio instance to use. WARNING: defaults to the public good Sigstore instance https://fulcio.sigstore.dev"),
        )
        sign_options.add_argument(
            "--oidc-issuer",
            metavar="URL",
            type=str,
            default="https://oauth2.sigstore.dev",
            help=_("The OpenID Connect issuer to use to sign the artifact"),
        )
        sign_options.add_argument(
            "--ctfe-pubkey",
            metavar="FILE",
            type=argparse.FileType("rb"),
            help=_("A PEM-encoded public key for the CT log"),
        )
        sign_options.add_argument(
            "--credentials-file-path",
            metavar="URL",
            type=str,
            default=None,
            help=_("Path to the OIDC client ID and client secret file on the server to authentify to Sigstore."),
        )
        sign_options.add_argument(
            "--enable-interactive",
            metavar="BOOL",
            type=bool,
            help=_("Enable Sigstore's interactive browser flow. Defaults to False."),
        )


    def handle(self, *args, **options):
        if "from_file" in options:
            file_path = Path(options["from_file"])

            with open(file_path, "r") as file:
                sigstore_config = json.load(file)
                SIGSTORE_CONFIGURATION_FILE_SCHEMA(sigstore_config)
                sign_options = sigstore_config["sign-options"]
                options = {option_name.replace("_", "-") : option_value for option_name, option_value in options.items()}
                for option_name, option_value in options.items():
                    if option_value:
                        sign_options[option_name] = option_value

                enable_interactive = _to_bool(sign_options["enable-interactive"])

                try:
                    SigstoreSigningService.objects.create(
                        name=sign_options["name"],
                        rekor_url=sign_options.get("rekor-url"),
                        oidc_issuer=sign_options.get("oidc-issuer"),
                        tuf_url=sign_options.get("tuf-url"),
                        rekor_root_pubkey=sign_options.get("rekor-root-pubkey"),
                        fulcio_url=sign_options.get("fulcio-url"),
                        ctfe_pubkey=sign_options.get("ctfe-pubkey"),
                        credentials_file_path=sign_options.get("credentials-file-path"),
                        enable_interactive=enable_interactive,
                    )

                    print(
                        f"Successfully configured the Sigstore signing service {sign_options['name']} with the following parameters: \n"
                        f"Rekor instance URL: {sign_options['rekor-url']}\n"
                        f"OIDC issuer: {sign_options.get('oidc-issuer')}\n"
                        f"TUF repository metadata URL: {sign_options['tuf-url']}\n"
                        f"Rekor root public key: {sign_options.get('rekor-root-pubkey')}\n"
                        f"Fulcio instance URL: {sign_options['fulcio-url']}\n"
                        f"Certificate Transparency log public key: {sign_options.get('ctfe-pubkey')}\n"
                        f"OIDC credentials file path: {sign_options['credentials-file-path']}\n"
                        f"Enable interactive signing: {enable_interactive}\n"
                    )

                except IntegrityError as e:
                    raise CommandError(str(e))