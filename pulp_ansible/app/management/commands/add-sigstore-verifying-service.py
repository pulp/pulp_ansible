from django.core.management import BaseCommand, CommandError
from django.db.utils import IntegrityError

import argparse
import json

from gettext import gettext as _
from pathlib import Path
from voluptuous import Optional, Required, Schema

from pulp_ansible.app.models import SigstoreVerifyingService


SIGSTORE_CONFIGURATION_FILE_SCHEMA = Schema(
    {
        Required("name"): str,
        Optional("rekor-url"): str,
        Optional("tuf-url"): str,
        Optional("rekor-root-pubkey"): str,
        Optional("expected-oidc-issuer"): str,
        Optional("expected-identity"): str,
        Optional("certificate-chain"): str,
        Optional("verify-offline"): bool,
    }
)

DEFAULTS = {
    "rekor-url": "https://rekor.sigstore.dev",
    "tuf-url": "https://tuf-repo-cdn.sigstore.dev/",
    "expected-oidc-issuer": None,
    "expected-identity": None,
    "rekor-root-pubkey": None,
    "certificate-chain": None,
    "verify-offline": False,
}


# https://github.com/sigstore/sigstore-python/blob/55f98f663721be34a5e5b63fb72e740c3d580f66/sigstore/_cli.py#L64
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
    Django management command for adding a Sigstore verifying service.
    This command is in tech preview.
    """

    help = "Adds a new Sigstore verifying service. [tech-preview]"

    def add_arguments(self, parser):
        verify_options = parser.add_argument_group("Sign options")
        verify_options.add_argument(
            "--from-file",
            help=_(
                "Load the Sigstore configuration from a JSON file. "
                "File configuration can be overriden by specified arguments.\n"
            ),
        )
        verify_options.add_argument(
            "--name",
            type=str,
            metavar="NAME",
            help=_("Name for registering the Sigstore verifying service.\n"),
        )
        verify_options.add_argument(
            "--rekor-url",
            metavar="URL",
            type=str,
            help=_(
                "The Rekor instance to use."
            ),
        )
        verify_options.add_argument(
            "--tuf-url",
            metavar="URL",
            type=str,
            help=_(
                "The TUF repository to use."
            ),
        )
        verify_options.add_argument(
            "--rekor-root-pubkey",
            metavar="FILE",
            type=argparse.FileType("rb"),
            help=_("A PEM-encoded root public key for Rekor itself"),
        )
        verify_options.add_argument(
            "--expected-oidc-issuer",
            metavar="URL",
            type=str,
            help=_("The OpenID Connect issuer that issued the signing certificate"),
        )
        verify_options.add_argument(
            "--expected-identity",
            metavar="IDENTITY",
            type=str,
            help=_("The expected signer email present in the signing certificate."),
        )
        verify_options.add_argument(
            "--certificate-chain",
            metavar="FILE",
            type=str,
            help=_(
                "Path to a list of CA certificates in PEM format which will be needed "
                "when building the certificate chain for the Fulcio signing certificate."
            ),
        )
        verify_options.add_argument(
            "--verify-offline",
            metavar="BOOL",
            type=bool,
            help=_("Verify the signature offline."),
        )

    def handle(self, *args, **options):
        verify_options = {}

        if "from_file" in options:
            file_path = Path(options["from_file"])

            with open(file_path, "r") as file:
                config = json.load(file)
                SIGSTORE_CONFIGURATION_FILE_SCHEMA(config)
                verify_options = config

        options = {
            option_name.replace("_", "-"): option_value
            for option_name, option_value in options.items()
        }
        for option_name, option_value in options.items():
            if option_value:
                verify_options[option_name] = option_value

        verify_offline = _to_bool(verify_options["verify-offline"])
        
        if not (verify_options.get("tuf-url") or verify_options.get("rekor-root-pubkey")):
            raise ValueError("No TUF URL or Rekor public key configured")

        try:
            SigstoreVerifyingService.objects.create(
                name=verify_options["name"],
                rekor_url=verify_options.get("rekor-url"),
                tuf_url=verify_options.get("tuf-url"),
                rekor_root_pubkey=verify_options.get("rekor-root-pubkey"),
                expected_oidc_issuer=verify_options.get("expected-oidc-issuer"),
                expected_identity=verify_options.get("expected-identity"),
                certificate_chain=verify_options.get("certificate-chain"),
                verify_offline=verify_offline,
            )

            print(
                "Successfully configured the Sigstore signing service "
                f"{verify_options['name']} with the following parameters: \n"
                f"Rekor instance URL: {verify_options['rekor-url']}\n"
                f"Expected OIDC issuer: {verify_options.get('expected-oidc-issuer')}\n"
                f"Expected identity: {verify_options.get('expected-identity')}\n"
                f"Certificate chain: {verify_options.get('certificate-chain')}\n"
                f"TUF repository metadata URL: {verify_options['tuf-url']}\n"
                f"Rekor root public key: {verify_options.get('rekor-root-pubkey')}\n"
                f"Verify offline: {verify_offline}\n"
            )

        except IntegrityError as e:
            raise CommandError(str(e))
