"""
Tasks related to Sigstore content signature and verification.
"""

import aiofiles
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import tarfile
import tempfile
import cryptography.x509 as x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from gettext import gettext as _

from ansible_sign.checksum import (
    ChecksumFile,
    ChecksumMismatch,
    InvalidChecksumLine,
)
from ansible_sign.checksum.differ import DistlibManifestChecksumFileExistenceDiffer

from sigstore.verify.models import VerificationFailure
from sigstore._internal.oidc import Identity
from sigstore._internal.sct import verify_sct
from sigstore._utils import sha256_streaming
from sigstore_protobuf_specs.dev.sigstore.bundle.v1 import Bundle

from pulpcore.plugin.stages import (
    ContentSaver,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)

from pulp_ansible.app.tasks.signature import SigningDeclarativeVersion

from django.conf import settings
from django.core.files.storage import default_storage as storage
from pulpcore.plugin.models import SigningService, ProgressReport
from pulpcore.plugin.sync import sync_to_async_iterable, sync_to_async
from pulpcore.plugin.util import gpg_verify
from pulpcore.plugin.exceptions import InvalidSignatureError
from pulp_ansible.app.tasks.utils import get_file_obj_from_tarball
from pulp_ansible.app.sigstore.exceptions import (
    MissingSigstoreVerificationMaterialsException,
    VerificationFailureException,
)
from rest_framework import serializers

from pulp_ansible.app.models import (
    CollectionVersion,
    CollectionVersionSignature,
    CollectionVersionSigstoreSignature,
    SigstoreSigningService,
)

log = logging.getLogger(__name__)


def _generate_checksum_manifest(cartifact):
    """
    Generate a file containing the sha256 hashes of all the collection elements.
    """
    artifact_name = cartifact.artifact.file.name
    artifact_file = storage.open(artifact_name)

    with tempfile.TemporaryDirectory() as tempdir:
        differ = DistlibManifestChecksumFileExistenceDiffer
        checksum = ChecksumFile(tempdir, differ=differ)
        with tarfile.open(fileobj=artifact_file, mode="r") as tar:
            tar.extractall(path=tempdir)

            try:
                manifest = checksum.generate_gnu_style()

            except FileNotFoundError as e:
                if os.path.islink(e.filename):
                    log.error(f"Broken symlink found at {e.filename} -- this is not supported. Aborting.")
                if e.filename.endswith("/MANIFEST.in"):
                    log.error("Could not find a MANIFEST.in file in the specified project.")
                    log.info("If you are attempting to sign a project, please create this file.")
                    log.info("See the ansible-sign documentation for more information.")
                raise e

            except DistlibException as e:
                log.error(f"An error was encountered while parsing MANIFEST.in: {e}")
                raise e

            for warning in checksum.warnings:
                log.warn(warning)
            log.debug(
                "Full calculated checksum manifest (%s):\n%s",
                manifest,
            )
            return manifest


def verify_sigstore_signature_upload(data):
    # Check that the provided signature materials correspond to the collection content on upload.
    """The task code for verifying Sigstore signature upload."""
    collection = data["signed_collection"]
    repository = data.get("repository")
    if repository:
        sigstore_verifying_service = repository.sigstore_verifying_service
    else:
        raise ValueError(
            "This content type must be associated with a repository."
        )
    signature = data["data"]
    certificate = data["sigstore_x509_certificate"]
    sigstore_bundle = data.get("sigstore_bundle")
    cartifact = collection.contentartifact_set.select_related("artifact").first()
    checksums = _generate_checksum_manifest(cartifact)

    if sigstore_bundle:
        bundle = Bundle().from_json(sigstore_bundle)

    with tempfile.NamedTemporaryFile(dir=".", delete=False, mode="w") as manifest_file:
        manifest_file.write(checksums)
        manifest_file.flush()
    with open(manifest_file.name, "rb", buffering=0) as manifest_io:
        try:
            verification_result = sigstore_verifying_service.sigstore_verify(
                manifest=manifest_io,
                signature=signature,
                certificate=certificate,
                sigstore_bundle=bundle,
            )
        except AttributeError as e:
            log.error(
                f"Error verifying sigstore signature for {collection}: "
                f"Repository {repository} is not configured with a SigstoreVerifyingService."
            )
            raise e

    if isinstance(verification_result, VerificationFailure):
        raise VerificationFailureException(
            "Failed to verify Sigstore signature for collection "
            f"{collection}: {verification_result.reason}"
        )

    print(f"Validated Sigstore signature for collection {collection}")

    data["data"] = signature
    data["sigstore_x509_certificate"] = certificate
    data["sigstore_signing_service"] = sigstore_signing_service

    return data


def sigstore_sign(repository_href, content_hrefs, sigstore_signing_service_href):
    """Signing task for Sigstore."""
    from pulp_ansible.app.models import AnsibleRepository

    repository = AnsibleRepository.objects.get(pk=repository_href)
    if content_hrefs == ["*"]:
        filtered = repository.latest_version().content.filter(
            pulp_type=CollectionVersion.get_pulp_type()
        )
        content = CollectionVersion.objects.filter(pk__in=filtered)
    else:
        content = CollectionVersion.objects.filter(pk__in=content_hrefs)
    sigstore_signing_service = SigstoreSigningService.objects.get(pk=sigstore_signing_service_href)
    filtered_sigs = repository.latest_version().content.filter(
        pulp_type=CollectionVersionSigstoreSignature.get_pulp_type()
    )
    repos_current_signatures = CollectionVersionSigstoreSignature.objects.filter(
        pk__in=filtered_sigs
    )
    first_stage = CollectionSigstoreSigningFirstStage(
        content, sigstore_signing_service, repos_current_signatures
    )
    SigningDeclarativeVersion(first_stage, repository).create()


class CollectionSigstoreSigningFirstStage(Stage):
    """
    This stage signs the content with Sigstore OIDC credentials provided on the Pulp server
    and creates CollectionVersionSigstoreSignatures.
    """

    def __init__(self, content, sigstore_signing_service, current_sigstore_signatures):
        """Initialize Sigstore signing first stage."""
        super().__init__()
        self.content = content
        self.sigstore_signing_service = sigstore_signing_service
        self.repos_current_sigstore_signatures = current_sigstore_signatures
        self.semaphore = asyncio.Semaphore(settings.ANSIBLE_SIGNING_TASK_LIMITER)

    async def sigstore_sign_collection_versions(self, collection_versions):
        """Signs the collection versions with Sigstore."""

        # Prepare ephemeral key pair and certificate and sign the collections asynchronously
        private_key = ec.generate_private_key(ec.SECP384R1())
        with open(self.sigstore_signing_service.credentials_file_path, "r") as credentials_file:
            credentials = json.load(credentials_file)
            client_id, client_secret = (
                credentials["keycloak_client_id"],
                credentials["keycloak_client_secret"],
            )
            identity_token = self.sigstore_signing_service.issuer.identity_token(
                client_id, client_secret, self.sigstore_signing_service.enable_interactive
            )
        oidc_identity = Identity(identity_token)

        # Build an X.509 Certificiate Signing Request
        builder = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name(
                    [
                        x509.NameAttribute(NameOID.EMAIL_ADDRESS, oidc_identity.proof),
                    ]
                )
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
        )
        certificate_request = builder.sign(private_key, hashes.SHA256())
        certificate_response = self.sigstore_signing_service.fulcio.signing_cert.post(
            certificate_request, identity_token
        )

        # Verify the SCT
        sct = certificate_response.sct
        cert = certificate_response.cert
        chain = certificate_response.chain

        verify_sct(sct, cert, chain, self.sigstore_signing_service.rekor._ct_keyring)

        # Limits the number of subprocesses spawned/running at one time
        async with self.semaphore:
            async for collection_version in collection_versions:
                # We create the checksums manifest to sign
                async with aiofiles.tempfile.NamedTemporaryFile(
                    dir=".", mode="w", delete=False
                ) as manifest_file:
                    cartifact = collection_version.contentartifact_set.select_related("artifact").first()
                    manifest_data = await sync_to_async(_generate_checksum_manifest)(cartifact)                    
                    await manifest_file.write(manifest_data)
                async with aiofiles.open(manifest_file.name, mode="rb", buffering=0) as iofile:
                    async with aiofiles.tempfile.NamedTemporaryFile(dir=".", mode="w", delete=False) as manifest_content:
                        content = await iofile.read()
                        manifest_content.write()
                    with open(manifest_content.name, "rb") as manifest_bytes:
                        input_digest = sha256_streaming(manifest_bytes)
                        result = await self.sigstore_signing_service.sigstore_asign(
                            input_digest, private_key, cert
                        )

                        sig_data, cert_data, bundle_data = (
                            result["signature"],
                            result["certificate"],
                            result["bundle"]
                        )

                    cv_signature = CollectionVersionSigstoreSignature(
                        data=sig_data,
                        sigstore_x509_certificate=cert_data,
                        sigstore_bundle=bundle_data,
                        signed_collection=collection_version,
                        sigstore_signing_service=self.sigstore_signing_service,
                    )
                    dc = DeclarativeContent(content=cv_signature)
                    await self.progress_report.aincrement()
                    await self.put(dc)

    async def run(self):
        """Sign collections with Sigstore if they have not been signed."""
        # Filter out any content that has not been signed with the Sigstore signing service.
        tasks = []
        current_signatures = CollectionVersionSigstoreSignature.objects.filter(
            sigstore_signing_service__name=self.sigstore_signing_service.name
        )
        # new_content = self.content.exclude(sigstore_signatures__in=current_signatures)
        new_content = self.content
        ntotal = await sync_to_async(new_content.count)()
        msg = _("Signing new CollectionVersions with Sigstore.")
        async with ProgressReport(message=msg, code="sign.new.signature", total=ntotal) as p:
            self.progress_report = p
            await asyncio.create_task(self.sigstore_sign_collection_versions(sync_to_async_iterable(new_content.iterator())))

        present_content = current_signatures.filter(signed_collection__in=self.content).exclude(
            pk__in=self.repos_current_sigstore_signatures
        )
        ptotal = await sync_to_async(present_content.count)()
        pmsg = _("Adding present CollectionVersionSigstoreSignatures")
        async with ProgressReport(message=pmsg, code="sign.present.signature", total=ptotal) as np:
            async for sigstore_signature in sync_to_async_iterable(present_content.iterator()):
                await np.aincrement()
                await self.put(DeclarativeContent(content=sigstore_signature))
