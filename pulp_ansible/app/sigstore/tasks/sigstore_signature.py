"""
Tasks related to Sigstore content signature and verification.
"""

import asyncio
import io
import json
import logging
import os
import re
import tarfile
import tempfile
from distlib.manifest import DistlibException
from gettext import gettext as _

from ansible_sign.checksum import (
    ChecksumFile,
)
from ansible_sign.checksum.differ import DistlibManifestChecksumFileExistenceDiffer

from sigstore.verify.models import VerificationFailure
from sigstore._utils import sha256_streaming
from sigstore_protobuf_specs.dev.sigstore.bundle.v1 import Bundle

from pulpcore.plugin.stages import (
    DeclarativeContent,
    Stage,
)

from pulp_ansible.app.tasks.signature import SigningDeclarativeVersion

from django.conf import settings
from django.core.files.storage import default_storage as storage
from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.sync import sync_to_async_iterable, sync_to_async
from pulp_ansible.app.sigstore.exceptions import VerificationFailureException

from pulp_ansible.app.models import (
    CollectionVersion,
    CollectionVersionSigstoreSignature,
    SigstoreSigningService,
)

log = logging.getLogger(__name__)


def _generate_checksum_manifest(collection_version):
    """
    Generate a file containing the sha256 hashes of all the collection elements.
    """
    cartifact = collection_version.contentartifact_set.select_related("artifact").first()
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
                    log.error(
                        f"Broken symlink found at {e.filename} -- this is not supported. Aborting."
                    )
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
    """
    The task code for verifying that the provided signature materials
    correspond to the collection content on upload.
    """
    collection = data["signed_collection"]
    repository = data.get("repository")
    if repository:
        sigstore_verifying_services = repository.sigstore_verifying_service.all()
        if not sigstore_verifying_services and settings.ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION:
            log.warn("Signature verification is required but no Sigstore verifying service configured for the repository.")
            return data
    else:
        raise ValueError("This content type must be associated with a repository.")
    sigstore_bundle = data.get("sigstore_bundle")
    checksums = io.BytesIO(_generate_checksum_manifest(collection).encode("utf-8"))

    bundle_bytes = json.dumps(sigstore_bundle).encode("utf-8")

    bundle = Bundle().from_json(bundle_bytes) if sigstore_bundle else None
    data["sigstore_signing_service"] = None

    for sigstore_verifying_service in sigstore_verifying_services:
        verification_result = sigstore_verifying_service.sigstore_verify(
            manifest=checksums,
            sigstore_bundle=bundle,
        )

        print("VERIFICATION RESULT: ", verification_result)

        if verification_result:
            log.info(f"Validated Sigstore signature for collection {collection}")
            return data

    if settings.ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION:
        raise VerificationFailureException(
            "Failed to verify Sigstore signature against all verifying services configured on this repository with ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION enabled."
        )

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
        # Get an OIDC token to authenticate to Fulcio
        client_secret = self.sigstore_signing_service.oidc_client_secret

        identity = self.sigstore_signing_service.issuer.identity_token(
            "sigstore", client_secret,
        )

        signing_ctx = self.sigstore_signing_service.signing_context

        with signing_ctx.signer(identity) as signer:
            # Limits the number of subprocesses spawned/running at one time
            async with self.semaphore:
                async for collection_version in collection_versions:
                    # We create the checksums manifest to sign
                    manifest_data = await sync_to_async(_generate_checksum_manifest)(collection_version)
                    input_digest = io.BytesIO(manifest_data.encode("utf-8"))

                    signing_result = await sync_to_async(signer.sign)(input_=input_digest)
                    bundle_data = signing_result.to_bundle().to_json()

                    cv_signature = CollectionVersionSigstoreSignature(
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
            await asyncio.create_task(
                self.sigstore_sign_collection_versions(
                    sync_to_async_iterable(new_content.iterator())
                )
            )

        present_content = current_signatures.filter(signed_collection__in=self.content).exclude(
            pk__in=self.repos_current_sigstore_signatures
        )
        ptotal = await sync_to_async(present_content.count)()
        pmsg = _("Adding present CollectionVersionSigstoreSignatures")
        async with ProgressReport(message=pmsg, code="sign.present.signature", total=ptotal) as np:
            async for sigstore_signature in sync_to_async_iterable(present_content.iterator()):
                await np.aincrement()
                await self.put(DeclarativeContent(content=sigstore_signature))
