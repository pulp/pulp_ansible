import aiofiles
import asyncio
import hashlib
import logging
import tarfile
import tempfile
from gettext import gettext as _

from pulpcore.plugin.stages import (
    ContentSaver,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)

from pulp_ansible.app.models import (
    AnsibleRepository,
    CollectionVersion,
    CollectionVersionSignature,
)

from django.conf import settings
from django.core.files.storage import default_storage as storage
from pulpcore.plugin.models import SigningService, ProgressReport
from pulpcore.plugin.sync import sync_to_async_iterable, sync_to_async
from pulpcore.plugin.util import gpg_verify
from pulpcore.plugin.exceptions import InvalidSignatureError
from pulp_ansible.app.tasks.utils import get_file_obj_from_tarball
from rest_framework import serializers


log = logging.getLogger(__name__)


def verify_signature_upload(data):
    """The task code for verifying collection signature upload."""
    file = data["file"]
    sig_data = file.read().decode()
    file.seek(0)
    collection = data["signed_collection"]
    repository = data.get("repository")
    gpgkey = repository and repository.gpgkey or ""

    artifact = collection.contentartifact_set.select_related("artifact").first().artifact.file.name
    artifact_file = storage.open(artifact)
    with tarfile.open(fileobj=artifact_file, mode="r") as tar:
        manifest = get_file_obj_from_tarball(tar, "MANIFEST.json", artifact_file)
        with tempfile.NamedTemporaryFile(dir=".") as manifest_file:
            manifest_file.write(manifest.read())
            manifest_file.flush()
            try:
                verified = gpg_verify(gpgkey, file, manifest_file.name)
            except InvalidSignatureError as e:
                if gpgkey:
                    raise serializers.ValidationError(
                        _("Signature verification failed: {}").format(e.verified.status)
                    )
                elif settings.ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION:
                    raise serializers.ValidationError(
                        _("Signature verification failed: No key available.")
                    )
                else:
                    # We have no key configured. So we simply accept the signature as is
                    verified = e.verified
                    log.warn(
                        "Collection Signature was accepted without verification. No key available."
                    )

    data["data"] = sig_data
    data["digest"] = file.hashers["sha256"].hexdigest()
    data["pubkey_fingerprint"] = verified.fingerprint
    return data


def sign(repository_href, content_hrefs, signing_service_href):
    """The signing task."""
    repository = AnsibleRepository.objects.get(pk=repository_href)
    if content_hrefs == ["*"]:
        filtered = repository.latest_version().content.filter(
            pulp_type=CollectionVersion.get_pulp_type()
        )
        content = CollectionVersion.objects.filter(pk__in=filtered)
    else:
        content = CollectionVersion.objects.filter(pk__in=content_hrefs)
    signing_service = SigningService.objects.get(pk=signing_service_href)
    filtered_sigs = repository.latest_version().content.filter(
        pulp_type=CollectionVersionSignature.get_pulp_type()
    )
    repos_current_signatures = CollectionVersionSignature.objects.filter(pk__in=filtered_sigs)
    first_stage = CollectionSigningFirstStage(content, signing_service, repos_current_signatures)
    SigningDeclarativeVersion(first_stage, repository).create()


class SigningDeclarativeVersion(DeclarativeVersion):
    """Custom signature pipeline."""

    def pipeline_stages(self, new_version):
        """The stages for the signing process."""
        pipeline = [
            self.first_stage,  # CollectionSigningFirstStage
            ContentSaver(),
        ]
        return pipeline


class CollectionSigningFirstStage(Stage):
    """
    This stage signs the content and creates CollectionVersionSignatures.
    """

    def __init__(self, content, signing_service, current_signatures):
        """Initialize Signing first stage."""
        super().__init__()
        self.content = content
        self.signing_service = signing_service
        self.repos_current_signatures = current_signatures
        self.semaphore = asyncio.Semaphore(settings.ANSIBLE_SIGNING_TASK_LIMITER)

    async def sign_collection_version(self, collection_version):
        """Signs the collection version."""

        def _extract_manifest():
            cartifact = collection_version.contentartifact_set.select_related("artifact").first()
            artifact_name = cartifact.artifact.file.name
            artifact_file = storage.open(artifact_name)
            with tarfile.open(fileobj=artifact_file, mode="r") as tar:
                manifest = get_file_obj_from_tarball(tar, "MANIFEST.json", artifact_name)
                return manifest.read()

        # Limits the number of subprocesses spawned/running at one time
        async with self.semaphore:
            # We use the manifest to create the signature
            # OpenPGP doesn't take filename into account for signatures, not sure about others
            async with aiofiles.tempfile.NamedTemporaryFile(dir=".", mode="wb") as m:
                manifest_data = await sync_to_async(_extract_manifest)()
                await m.write(manifest_data)
                await m.flush()
                result = await self.signing_service.asign(m.name)
            async with aiofiles.open(result["signature"], "rb") as sig:
                data = await sig.read()
            cv_signature = CollectionVersionSignature(
                data=data.decode(),
                digest=hashlib.sha256(data).hexdigest(),
                signed_collection=collection_version,
                pubkey_fingerprint=self.signing_service.pubkey_fingerprint,
                signing_service=self.signing_service,
            )
            dc = DeclarativeContent(content=cv_signature)
            await self.progress_report.aincrement()
            await self.put(dc)

    async def run(self):
        """Signs collections if they have not been signed with key."""
        tasks = []
        # Filter out any content that already has a signature with pubkey_fingerprint
        current_signatures = CollectionVersionSignature.objects.filter(
            pubkey_fingerprint=self.signing_service.pubkey_fingerprint
        )
        new_content = self.content.exclude(signatures__in=current_signatures)
        ntotal = await sync_to_async(new_content.count)()
        nmsg = _("Signing new CollectionVersions")
        async with ProgressReport(message=nmsg, code="sign.new.signature", total=ntotal) as p:
            self.progress_report = p
            async for collection_version in sync_to_async_iterable(new_content.iterator()):
                tasks.append(asyncio.create_task(self.sign_collection_version(collection_version)))
            await asyncio.gather(*tasks)

        # Add any signatures already present in Pulp if part of content list
        present_content = current_signatures.filter(signed_collection__in=self.content).exclude(
            pk__in=self.repos_current_signatures
        )
        ptotal = await sync_to_async(present_content.count)()
        pmsg = _("Adding present CollectionVersionSignatures")
        async with ProgressReport(message=pmsg, code="sign.present.signature", total=ptotal) as np:
            async for signature in sync_to_async_iterable(present_content.iterator()):
                await np.aincrement()
                await self.put(DeclarativeContent(content=signature))
