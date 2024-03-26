from django.core.management import BaseCommand, CommandError
from django.db.utils import IntegrityError

import argparse
import json

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
        Optional("oidc-client-secret"): str,
    }
)

DEFAULTS = {
    "rekor-url": "https://rekor.sigstore.dev",
    "tuf-url": "https://sigstore-tuf-root.storage.googleapis.com/",
    "fulcio-url": "https://fulcio.sigstore.dev",
    "oidc-issuer": "https://oauth2.sigstore.dev",
    "rekor-root-pubkey": None,
    "ctfe-pubkey": None,
    "oidc-client-secret": None,
}


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
            help=_(
                "Load the Sigstore configuration from a JSON file. "
                "File configuration can be overriden by specified arguments.\n"
            ),
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
            help=_("The Rekor instance to use."),
        )
        sign_options.add_argument(
            "--tuf-url",
            metavar="URL",
            type=str,
            help=_("The TUF repository to use."),
        )
        sign_options.add_argument(
            "--rekor-root-pubkey",
            metavar="FILE",
            type=argparse.FileType("rb"),
            help=_("A PEM-encoded root public key for Rekor itself"),
        )
        sign_options.add_argument(
            "--fulcio-url",
            metavar="URL",
            type=str,
            help=_("The Fulcio instance to use."),
        )
        sign_options.add_argument(
            "--oidc-issuer",
            metavar="URL",
            type=str,
            help=_("The OpenID Connect issuer to use to sign the artifact"),
        )
        sign_options.add_argument(
            "--ctfe-pubkey",
            metavar="FILE",
            type=argparse.FileType("rb"),
            help=_("A PEM-encoded public key for the CT log"),
        )
        sign_options.add_argument(
            "--oidc-client-secret",
            metavar="URL",
            type=str,
            help=_("The OIDC client secret to use to authenticate to Sigstore."),
        )

    def handle(self, *args, **options):
        sign_options = {}

        if "from_file" in options:
            file_path = Path(options["from_file"])

            with open(file_path, "r") as file:
                config = json.load(file)
                SIGSTORE_CONFIGURATION_FILE_SCHEMA(config)
                sign_options = config

        options = {
            option_name.replace("_", "-"): option_value
            for option_name, option_value in options.items()
        }
        for option_name, option_value in options.items():
            if option_value:
                sign_options[option_name] = option_value

        if not (sign_options.get("tuf-url") or sign_options.get("rekor-root-pubkey")):
            raise ValueError("No TUF URL or Rekor public key configured")

        try:
            SigstoreSigningService.objects.create(
                name=sign_options["name"],
                rekor_url=sign_options.get("rekor-url"),
                oidc_issuer=sign_options.get("oidc-issuer"),
                tuf_url=sign_options.get("tuf-url"),
                rekor_root_pubkey=sign_options.get("rekor-root-pubkey"),
                fulcio_url=sign_options.get("fulcio-url"),
                ctfe_pubkey=sign_options.get("ctfe-pubkey"),
                oidc_client_secret=sign_options.get("oidc-client-secret"),
            )

            print(
                "Successfully configured the Sigstore signing service "
                f"{sign_options['name']} with the following parameters: \n"
                f"Rekor instance URL: {sign_options['rekor-url']}\n"
                f"OIDC issuer: {sign_options.get('oidc-issuer')}\n"
                f"TUF repository metadata URL: {sign_options.get('tuf-url')}\n"
                f"Rekor root public key: {sign_options.get('rekor-root-pubkey')}\n"
                f"Fulcio instance URL: {sign_options['fulcio-url']}\n"
                f"Certificate Transparency log public key: {sign_options.get('ctfe-pubkey')}\n"
            )

        except IntegrityError as e:
            raise CommandError(str(e))
