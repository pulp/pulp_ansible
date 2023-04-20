import aiohttp
import base64
import hashlib
import json
import os
import re
import requests
import tempfile
from cryptography.hazmat.primitives import (
    hashes,
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.x509 import load_pem_x509_certificates
from gettext import gettext as _
from logging import getLogger
from urllib.parse import urljoin

from semantic_version import Version

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import JSONField, UniqueConstraint, Q
from django.db.utils import IntegrityError
from django.contrib.postgres import fields as psql_fields
from django.contrib.postgres import search as psql_search
from django_lifecycle import (
    AFTER_UPDATE,
    AFTER_DELETE,
    AFTER_CREATE,
    BEFORE_UPDATE,
    BEFORE_SAVE,
    hook,
)

from pulpcore.plugin.models import (
    AutoAddObjPermsMixin,
    BaseModel,
    Content,
    Remote,
    Repository,
    RepositoryVersion,
    Distribution,
    SigningService,
    Task,
    EncryptedTextField,
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_repo_version
from pulpcore.plugin.sync import sync_to_async

from pulp_ansible.app.sigstore.exceptions import MissingIdentityToken
from pulp_ansible.app.sigstore.issuers.keycloak import Keycloak

from sigstore._internal.ctfe import CTKeyring
from sigstore._internal.oidc.ambient import detect_gcp
from sigstore._internal.fulcio.client import FulcioClient
from sigstore._internal.keyring import Keyring
from sigstore._internal.rekor.client import (
    RekorClient,
    RekorClientError,
    RekorKeyring,
)
from sigstore._internal.tuf import TrustUpdater
from sigstore._utils import PEMCert
from sigstore.oidc import Issuer as PublicIssuer
from sigstore.sign import (
    Signer,
    SigningResult,
)
from sigstore.transparency import LogEntry
from sigstore.verify.verifier import (
    Verifier,
    VerificationMaterials,
)
from sigstore.verify.policy import Identity

from .downloaders import AnsibleDownloaderFactory


log = getLogger(__name__)


class Role(Content):
    """
    A content type representing a Role.
    """

    TYPE = "role"

    namespace = models.CharField(max_length=64)
    name = models.CharField(max_length=64)
    version = models.CharField(max_length=128, db_collation="pulp_ansible_semver")

    @property
    def relative_path(self):
        """
        Return the relative path of the ContentArtifact.
        """
        return self.contentartifact_set.get().relative_path

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("version", "name", "namespace")


class Collection(BaseModel):
    """A model representing a Collection."""

    namespace = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=64, editable=False)

    def __str__(self):
        """Return a representation."""
        return f"<{self.__class__.__name__}: {self.namespace}.{self.name}>"

    class Meta:
        unique_together = ("namespace", "name")


class CollectionImport(models.Model):
    """A model representing a collection import task details."""

    task = models.OneToOneField(
        Task, on_delete=models.CASCADE, editable=False, related_name="+", primary_key=True
    )
    messages = models.JSONField(default=list, editable=False)

    class Meta:
        ordering = ["task__pulp_created"]

    def add_log_record(self, log_record):
        """
        Records a single log message but does not save the CollectionImport object.

        Args:
            log_record(logging.LogRecord): The logging record to record on messages.

        """
        self.messages.append(
            {"message": log_record.msg, "level": log_record.levelname, "time": log_record.created}
        )


class Tag(BaseModel):
    """A model representing a Tag.

    Fields:

        name (models.CharField): The Tag's name.
    """

    name = models.CharField(max_length=64, unique=True, editable=False)

    def __str__(self):
        """Returns tag name."""
        return self.name


class AnsibleNamespace(BaseModel):
    """
    A model representing a Namespace. This should be used for permissions.
    """

    name = models.CharField(max_length=64, unique=True, editable=True)


class CollectionVersion(Content):
    """
    A content type representing a CollectionVersion.

    This model is primarily designed to adhere to the data format for Collection content. That spec
    is here: https://docs.ansible.com/ansible/devel/dev_guide/collections_galaxy_meta.html

    Fields:

        authors (psql_fields.ArrayField): A list of the CollectionVersion content's authors.
        contents (models.JSONField): A JSON field with data about the contents.
        dependencies (models.JSONField): A dict declaring Collections that this collection
            requires to be installed for it to be usable.
        description (models.TextField): A short summary description of the collection.
        docs_blob (models.JSONField): A JSON field holding the various documentation blobs in
            the collection.
        manifest (models.JSONField): A JSON field holding MANIFEST.json data.
        files (models.JSONField): A JSON field holding FILES.json data.
        documentation (models.CharField): The URL to any online docs.
        homepage (models.CharField): The URL to the homepage of the collection/project.
        issues (models.CharField): The URL to the collection issue tracker.
        license (psql_fields.ArrayField): A list of licenses for content inside of a collection.
        name (models.CharField): The name of the collection.
        namespace (models.CharField): The namespace of the collection.
        repository (models.CharField): The URL of the originating SCM repository.
        version (models.CharField): The version of the collection.
        requires_ansible (models.CharField): The version of Ansible required to use the collection.
        is_highest (models.BooleanField): Indicates that the version is the highest one
            in the collection. Import and sync workflows update this field, which then
            triggers the database to [re]build the search_vector.

    Relations:

        collection (models.ForeignKey): Reference to a collection model.
        tag (models.ManyToManyField): A symmetric reference to the Tag objects.
    """

    TYPE = "collection_version"

    # Data Fields
    authors = psql_fields.ArrayField(models.CharField(max_length=64), default=list, editable=False)
    contents = models.JSONField(default=list, editable=False)
    dependencies = models.JSONField(default=dict, editable=False)
    description = models.TextField(default="", blank=True, editable=False)
    docs_blob = models.JSONField(default=dict, editable=False)
    manifest = models.JSONField(default=dict, editable=False)
    files = models.JSONField(default=dict, editable=False)
    documentation = models.CharField(default="", blank=True, max_length=2000, editable=False)
    homepage = models.CharField(default="", blank=True, max_length=2000, editable=False)
    issues = models.CharField(default="", blank=True, max_length=2000, editable=False)
    license = psql_fields.ArrayField(models.CharField(max_length=32), default=list, editable=False)
    name = models.CharField(max_length=64, editable=False)
    namespace = models.CharField(max_length=64, editable=False)
    repository = models.CharField(default="", blank=True, max_length=2000, editable=False)
    requires_ansible = models.CharField(null=True, max_length=255)

    version = models.CharField(max_length=128, db_collation="pulp_ansible_semver")
    version_major = models.IntegerField()
    version_minor = models.IntegerField()
    version_patch = models.IntegerField()
    version_prerelease = models.CharField(max_length=128)

    is_highest = models.BooleanField(editable=False, default=False)

    # Foreign Key Fields
    collection = models.ForeignKey(
        Collection, on_delete=models.PROTECT, related_name="versions", editable=False
    )
    tags = models.ManyToManyField(Tag, editable=False)

    # Search Fields
    #   This field is populated by a trigger setup in the database by
    #   a migration file. The trigger only runs when the table is
    #   updated. CollectionVersions are INSERT'ed into the table, so
    #   the search_vector does not get populated at initial creation
    #   time. In the import or sync workflows, is_highest gets toggled
    #   back and forth, which causes an UPDATE operation and then the
    #   search_vector is built.
    search_vector = psql_search.SearchVectorField(default="")

    @hook(BEFORE_SAVE)
    def calculate_version_parts(self):
        v = Version(self.version)

        self.version_major = v.major
        self.version_minor = v.minor
        self.version_patch = v.patch
        self.version_prerelease = ".".join(v.prerelease)

    @property
    def relative_path(self):
        """
        Return the relative path for the ContentArtifact.
        """
        return "{namespace}-{name}-{version}.tar.gz".format(
            namespace=self.namespace, name=self.name, version=self.version
        )

    def __str__(self):
        """Return a representation."""
        return f"<{self.__class__.__name__}: {self.namespace}.{self.name} {self.version}>"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("namespace", "name", "version")
        constraints = [
            UniqueConstraint(
                fields=("collection", "is_highest"),
                name="unique_is_highest",
                condition=Q(is_highest=True),
            )
        ]


class CollectionVersionMark(Content):
    """
    A content type representing a mark that is attached to a content unit.

    Fields:
        value (models.CharField): The value of the mark.
        marked_collection (models.ForeignKey): Reference to a CollectionVersion.
    """

    PROTECTED_FROM_RECLAIM = False
    TYPE = "collection_mark"

    value = models.SlugField()
    marked_collection = models.ForeignKey(
        CollectionVersion, null=False, on_delete=models.CASCADE, related_name="marks"
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("value", "marked_collection")


class CollectionVersionSignature(Content):
    """
    A content type representing a signature that is attached to a content unit.

    Fields:
        data (models.TextField): A signature, base64 encoded. # Not sure if it is base64 encoded
        digest (models.CharField): A signature sha256 digest.
        pubkey_fingerprint (models.CharField): A fingerprint of the public key used.

    Relations:
        signed_collection (models.ForeignKey): A collection version this signature is relevant to.
        signing_service (models.ForeignKey): An optional signing service used for creation.
    """

    PROTECTED_FROM_RECLAIM = False
    TYPE = "collection_signature"

    signed_collection = models.ForeignKey(
        CollectionVersion, on_delete=models.CASCADE, related_name="signatures"
    )
    data = models.TextField()
    digest = models.CharField(max_length=64)
    pubkey_fingerprint = models.CharField(max_length=64)
    signing_service = models.ForeignKey(
        SigningService, on_delete=models.SET_NULL, related_name="signatures", null=True
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("pubkey_fingerprint", "signed_collection")



class SigstoreSigningService(Content):
    """
    A service to generate Sigstore signatures for a given CollectionVersion.
    Distinct from SigningService objects used to sign artifacts using GPG
    (does not call an external script provided by the user, but still needs to be registered).
    Fields:
        name (models.CharField):
            Name of the Sigstore signing service.
        rekor_url (models.TextField):
            The URL of the Rekor instance to use for logging signatures.
            Defaults to the Rekor public good instance URL (https://rekor.sigstore.dev).
        rekor_root_pubkey (models.TextField):
            A PEM-encoded root public key for Rekor itself.
        fulcio_url (models.TextField):
            The URL of the Fulcio instance to use for getting signing certificates.
            Defaults to the Fulcio public good instance URL (https://fulcio.sigstore.dev).
        tuf_url (models.TextField):
            The URL of the TUF metadata repository instance to use.
            Defaults to the public TUF instance URL
            (https://sigstore-tuf-root.storage.googleapis.com/).
        oidc_issuer (models.TextField):
            The OpenID Connect issuer to use for signing.
            Defaults to the public OAuth2 server URL (https://oauth2.sigstore.dev/auth).
        credentials_file_path (models.TextField):
            Path to the OIDC client ID and client secret file on the server
            to authentify to Sigstore.
        ctfe_pubkey (models.TextField):
            A PEM-encoded public key for the CT log.
        cert_identity (models.TextField):
            A unique identity string corresponding to the OIDC identity
            present as the SAN in the X509 certificate.
        enable_interactive (models.BooleanField):
            Enable Sigstore's interactive browser flow.
            Defaults to False.
    """

    TYPE = "sigstore_signing_service"

    PUBLIC_OIDC_ISSUERS = (
        "https://accounts.google.com",
        "https://oauth2.sigstore.dev/auth",
        "http://dex-idp:8888/auth",
    )
    PUBLIC_REKOR_URL = "https://rekor.sigstore.dev"
    PUBLIC_FULCIO_URL = "https://fulcio.sigstore.dev"
    PUBLIC_TUF_URL = "https://sigstore-tuf-root.storage.googleapis.com/"
    PUBLIC_ISSUER_URL = "https://oauth2.sigstore.dev/auth"

    name = models.CharField(db_index=True, unique=True, max_length=64)
    rekor_url = models.TextField(default=PUBLIC_REKOR_URL)
    rekor_root_pubkey = models.TextField(null=True)
    fulcio_url = models.TextField(default=PUBLIC_FULCIO_URL)
    tuf_url = models.TextField(default=PUBLIC_TUF_URL)
    oidc_issuer = models.TextField(default=PUBLIC_ISSUER_URL)
    credentials_file_path = models.TextField(null=True)
    ctfe_pubkey = models.TextField(null=True)
    enable_interactive = models.BooleanField(default=False)

    @property
    def fulcio(self):
        """Get a Fulcio instance."""
        return FulcioClient(url=self.fulcio_url)

    @property
    def ctfe_public_keys(self):
        """Get the CTFE public keys."""
        if self.ctfe_pubkey:
            return bytes(self.ctfe_pubkey, "utf-8")
        return self.trust_updater.get_ctfe_keys()

    @property
    def rekor_public_keys(self):
        """Get the Rekor instance public key."""
        if self.rekor_root_pubkey:
            return bytes(self.rekor_root_pubkey, "utf-8")
        return self.trust_updater.get_rekor_keys()

    @property
    def rekor(self):
        """Get a Rekor instance."""
        if self.rekor_url == self.PUBLIC_REKOR_URL:
            return RekorClient.production(self.trust_updater)

        rekor_key = RekorKeyring(Keyring([self.rekor_public_keys]))
        ctfe_key = CTKeyring(Keyring([self.ctfe_public_keys]))
        return RekorClient(
            self.rekor_url,
            rekor_key,
            ctfe_key,
        )

    @property
    def issuer(self):
        """Get an OIDC issuer instance."""
        if self.oidc_issuer in self.PUBLIC_OIDC_ISSUERS:
            return PublicIssuer(self.oidc_issuer)
        return Keycloak(self.oidc_issuer)

    @property
    def trust_updater(self):
        """Get a custom TrustUpdater instance depending on the TUF metadata repository provided."""
        return TrustUpdater(self.tuf_url)

    @property
    def signer(self):
        """Get a Signer instance."""
        return Signer(
            self.fulcio,
            self.rekor,
        )

    def sigstore_sign(self, input_bytes):
        """Sign collections with Sigstore."""
        signing_result = {}
        issuer = self.issuer

        if isinstance(issuer, PublicIssuer):
            issuer = self.issuer
            identity_token = issuer.identity_token()
        else:
            with open(self.credentials_file_path, "r") as credentials_file:
                credentials = json.load(credentials_file)
                client_id, client_secret = (
                    credentials["keycloak_client_id"],
                    credentials["keycloak_client_secret"],
                )
            if isinstance(issuer, Keycloak):
                identity_token = issuer.identity_token(
                    client_id, client_secret, self.enable_interactive
                )

        if not identity_token:
            raise MissingIdentityToken(
                "Sigstore signing failed: OIDC identity token could not be retrieved."
            )

        log.info("Signing artifact checksum file")

        result = self.signer.sign(
            input=input_bytes,
            identity_token=identity_token,
        )

        log.info(f"Using ephemeral certificate: {result.cert_pem}")
        log.info(f"Transparency log entry created at index: {result.log_entry.log_index}")
        signing_result["signature"] = result.b64_signature
        signing_result["certificate"] = result.cert_pem
        signing_result["bundle"] = result._to_bundle().to_json()

        return signing_result

    async def sigstore_asign(self, input_digest, private_key, cert):
        """Sign collections with Sigstore asynchronously."""
        b64_cert = base64.b64encode(cert.public_bytes(encoding=serialization.Encoding.PEM))
        signing_result = {}
        artifact_signature = await sync_to_async(private_key.sign)(
            input_digest, ec.ECDSA(Prehashed(hashes.SHA256()))
        )
        b64_artifact_signature = base64.b64encode(artifact_signature).decode()
        rekor_post_entry_payload = {
            "kind": "hashedrekord",
            "apiVersion": "0.0.1",
            "spec": {
                "signature": {
                    "content": b64_artifact_signature,
                    "publicKey": {"content": b64_cert.decode()},
                },
                "data": {"hash": {"algorithm": "sha256", "value": input_digest.hex()}},
            },
        }

        rekor_post_entries_url = urljoin(self.rekor.url, "log/entries/")

        async with aiohttp.ClientSession(
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        ) as session:
            try:
                async with session.post(
                    rekor_post_entries_url, json=rekor_post_entry_payload
                ) as resp:
                    rekor_response = await resp.json()
            except aiohttp.web.HTTPError as http_error:
                raise RekorClientError from http_error

        log_entry = LogEntry._from_response(rekor_response)
        log.info(f"Transparency log entry created with index: {log_entry.log_index}")

        result = SigningResult(
            input_digest=input_digest.hex(),
            cert_pem=PEMCert(
                cert.public_bytes(encoding=serialization.Encoding.PEM).decode()
            ),
            b64_signature=b64_artifact_signature,
            log_entry=log_entry,
        )

        signing_result["signature"] = result.b64_signature
        signing_result["certificate"] = result.cert_pem
        signing_result["bundle"] = result._to_bundle().to_json()

        return signing_result

    def save(self, *args, **kwargs):
        """Override the base `save` method to properly format PEM-encoded files."""
        def format(pubkey):
            delimiter = "-----"
            s = pubkey.split(delimiter)
            return delimiter + s[1] + delimiter + s[2].replace(" ", "\n") + delimiter + s[3] + delimiter
        if self.ctfe_pubkey:
            self.ctfe_pubkey = format(self.ctfe_pubkey)
        if self.rekor_root_pubkey:
            self.rekor_root_pubkey = format(self.rekor_root_pubkey)
        super(SigstoreSigningService, self).save(*args, **kwargs)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class SigstoreVerifyingService(Content):
    """
    A service to verify a CollectionVersion Sigstore signature.
    Fields:
        name (models.CharField):
            Name of the Sigstore verifying service.
        rekor_url (models.TextField):
            The URL of the Rekor instance to use for checking signature logs.
            Defaults to the Rekor public good instance URL (https://rekor.sigstore.dev).
        rekor_root_pubkey (models.TextField):
            A PEM-encoded root public key for Rekor itself.
            Defaults to None.
        certificate_chain (models.TextField):
            A list of PEM-encoded CA certificates needed to build the Fulcio signing certificate chain.
            Defaults to None.
        expected_oidc_issuer (models.TextField):
            The expected OIDC issuer in the signing certificate.
        expected_identity (models.TextField):
            The expected identity in the signing certificate.
        verify_offline (models.BooleanField):
            Verify the signature offline.
            Needs the presence of a Sigstore bundle in the verification materials.
    """

    TYPE = "sigstore_verifying_service"

    # TODO: dedupe public URL

    PUBLIC_REKOR_URL = "https://rekor.sigstore.dev"

    name = models.CharField(db_index=True, unique=True, max_length=64)
    rekor_url = models.TextField(default=PUBLIC_REKOR_URL)
    rekor_root_pubkey = models.TextField(null=True)
    certificate_chain = models.TextField(null=True)
    expected_oidc_issuer = models.TextField()
    expected_identity = models.TextField()
    verify_offline = models.BooleanField(null=True, default=False)

    @property
    def rekor_public_keys(self):
        """Get the Rekor instance public key."""
        if self.rekor_root_pubkey:
            return bytes(self.rekor_root_pubkey, "utf-8")
        return self.trust_updater.get_rekor_keys()

    @property
    def rekor(self):
        """Get a Rekor instance."""
        if self.rekor_url == self.PUBLIC_REKOR_URL:
            return RekorClient.production(self.trust_updater)

        rekor_key = RekorKeyring(Keyring([self.rekor_public_keys]))
        ctfe_key = CTKeyring(Keyring())
        return RekorClient(
            self.rekor_url,
            rekor_key,
            ctfe_key,
        )

    @property
    def certificates_chain(self):
        """Get the Fulcio certificate chain."""
        with tempfile.NamedTemporaryFile(dir=".", delete=False, mode="w") as certificates_file:
            certificates_file.write(self.certificate_chain)
            certificates_file.flush()
        with open(certificates_file.name, "rb") as bcertificates_file:
            return load_pem_x509_certificates(bcertificates_file.read())

    @property
    def verifier(self):
        """Get a Verifier instance."""
        return Verifier(
            rekor=self.rekor,
            fulcio_certificate_chain=self.certificates_chain,
        )

    def sigstore_verify(self, manifest, signature, certificate, sigstore_bundle=None):
        """Verify a Sigstore signature validity."""
        if self.verify_offline and not sigstore_bundle:
            raise ValueError(
                "Offline verification requires a Sigstore bundle."
            )

        if self.verify_offline and sigstore_bundle:
            verification_materials = VerificationMaterials.from_bundle(
                input_=manifest, bundle=sigstore_bundle, offline=True
            )
        else:
            verification_materials = VerificationMaterials(
                input_=manifest,
                cert_pem=certificate,
                signature=signature,
                rekor_entry=None,
                offline=False,
            )

        policy = Identity(
            identity=self.expected_identity,
            issuer=self.expected_oidc_issuer,
        )
        return self.verifier.verify(materials=verification_materials, policy=policy)

    def save(self, *args, **kwargs):
        """Override the base `save` method to properly format PEM-encoded files."""
        def format(pubkey):
            delimiter = "-----"
            s = pubkey.split(delimiter)
            res = delimiter + s[1] + delimiter +re.sub(' +', '\n', s[2]) + delimiter + s[3] + delimiter
            return res

        if self.certificate_chain:
            self.certificate_chain = format(self.certificate_chain)
        if self.rekor_root_pubkey:
            self.rekor_root_pubkey = format(self.rekor_root_pubkey)
        super(SigstoreVerifyingService, self).save(*args, **kwargs)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class CollectionVersionSigstoreSignature(Content):
    """
    A content type representing a Sigstore signature attached to a content unit.
    Fields:
        data (models.CharField):
            A signature, base64 encoded.
        sigstore_x509_certificate (models.TextField):
            The ephemeral PEM-encoded signing certificate generated by Sigstore.
        sigstore_bundle (models.JSONField):
            An optional Sigstore bundle used for offline verification.
    Relations:
        signed_collection (models.ForeignKey):
            A collection version this signature is relevant to.
        sigstore_signing_service (models.ForeignKey):
            The Sigstore Siging Service used for signing the collection version.
    """

    TYPE = "collection_sigstore_signatures"

    data = models.CharField(max_length=256)
    sigstore_x509_certificate = models.TextField()
    sigstore_bundle = models.JSONField(null=True)
    signed_collection = models.ForeignKey(
        CollectionVersion, on_delete=models.CASCADE, related_name="sigstore_signatures"
    )
    sigstore_signing_service = models.ForeignKey(
        SigstoreSigningService,
        on_delete=models.SET_NULL,
        related_name="sigstore_signatures",
        null=True,
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("sigstore_x509_certificate", "signed_collection")


class AnsibleNamespaceMetadata(Content):
    """
    A content type representing the Namespace metadata of a Collection.

    Namespace metadata can have an avatar which is stored as an associated artifact upon upload.

    Fields:
        name (models.CharField): The required name of the Namespace
        company (models.CharField): Optional namespace owner company name.
        email (models.CharField): Optional namespace contact email.
        description (models.CharField): Namespace brief description.
        resources (models.TextField): Namespace resources page in markdown format.
        links (psql_fields.HStore): Labeled related links.
        avatar_sha256 (models.CharField): SHA256 digest of avatar image.
        metadata_sha256(models.CharField): SHA256 digest of all other metadata fields.

    Relations:
        namespace (AnsibleNamespace): A link to the Namespace model used for permissions.
    """

    TYPE = "namespace"
    repo_key_fields = ("name",)
    # fields on the existing model in galaxy_ng
    name = models.CharField(max_length=64, blank=False)
    company = models.CharField(max_length=64, blank=True, default="")
    email = models.CharField(max_length=256, blank=True, default="")
    description = models.CharField(max_length=256, blank=True, default="")
    resources = models.TextField(blank=True, default="")

    links = psql_fields.HStoreField(default=dict)
    avatar_sha256 = models.CharField(max_length=64, null=True)

    # Hash of the values of all the fields mentioned above.
    # Content uniqueness constraint.
    metadata_sha256 = models.CharField(max_length=64, db_index=True, blank=False)
    namespace = models.ForeignKey(
        AnsibleNamespace, on_delete=models.PROTECT, related_name="metadatas"
    )

    @property
    def avatar_artifact(self):
        if self.avatar_sha256:
            avatar = self._artifacts.filter(sha256=self.avatar_sha256).first()
            if avatar is None:
                log.debug(
                    f"Artifact({self.avatar_sha256}) is missing for namespace avatar "
                    f"{self.name}:{self.metadata_sha256}"
                )
            return avatar

        return None

    @hook(BEFORE_SAVE)
    def calculate_metadata_sha256(self):
        """Calculates the metadata_sha256 from the other metadata fields."""
        metadata = {
            "name": self.name,
            "company": self.company,
            "email": self.email,
            "description": self.description,
            "resources": self.resources,
            "links": self.links,
            "avatar_sha256": self.avatar_sha256,
        }

        metadata_json = json.dumps(metadata, sort_keys=True).encode("utf-8")
        hasher = hashlib.sha256(metadata_json)
        if self.metadata_sha256:
            # If we are creating from sync, assert that calculated hash == synced hash
            if self.metadata_sha256 != hasher.hexdigest():
                raise IntegrityError("Calculated digest does not equal passed in digest")
        self.metadata_sha256 = hasher.hexdigest()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("metadata_sha256",)


class DownloadLog(BaseModel):
    """
    A download log for content units by user, IP and org_id.
    """

    content_unit = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="download_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        related_name="download_logs",
    )
    ip = models.GenericIPAddressField()
    extra_data = models.JSONField(null=True)
    user_agent = models.TextField()
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="download_logs"
    )
    repository_version = models.ForeignKey(
        RepositoryVersion, null=True, on_delete=models.SET_NULL, related_name="download_logs"
    )


class CollectionDownloadCount(BaseModel):
    """
    Aggregate count of downloads per collection
    """

    namespace = models.CharField(max_length=64, editable=False, db_index=True)
    name = models.CharField(max_length=64, editable=False, db_index=True)
    download_count = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ("namespace", "name")


class RoleRemote(Remote, AutoAddObjPermsMixin):
    """
    A Remote for Ansible content.
    """

    TYPE = "role"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [("manage_roles_roleremote", "Can manage roles on role remotes")]


class CollectionRemote(Remote, AutoAddObjPermsMixin):
    """
    A Remote for Collection content.
    """

    TYPE = "collection"

    requirements_file = models.TextField(null=True)
    auth_url = models.CharField(null=True, max_length=255)
    token = EncryptedTextField(null=True)
    sync_dependencies = models.BooleanField(default=True)
    signed_only = models.BooleanField(default=False)

    @property
    def download_factory(self):
        """
        Return the DownloaderFactory which can be used to generate asyncio capable downloaders.

        Upon first access, the DownloaderFactory is instantiated and saved internally.

        Plugin writers are expected to override when additional configuration of the
        DownloaderFactory is needed.

        Returns:
            DownloadFactory: The instantiated DownloaderFactory to be used by
                get_downloader()

        """
        try:
            return self._download_factory
        except AttributeError:
            self._download_factory = AnsibleDownloaderFactory(self)
            return self._download_factory

    @hook(
        AFTER_UPDATE,
        when_any=["url", "requirements_file", "sync_dependencies", "signed_only"],
        has_changed=True,
    )
    def _reset_repository_last_synced_metadata_time(self):
        AnsibleRepository.objects.filter(
            remote_id=self.pk, last_synced_metadata_time__isnull=False
        ).update(last_synced_metadata_time=None)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = (("manage_roles_collectionremote", "Can manage roles on collection remotes"),)


class GitRemote(Remote, AutoAddObjPermsMixin):
    """
    A Remote for Collection content hosted in Git repositories.
    """

    TYPE = "git"

    metadata_only = models.BooleanField(default=False)
    git_ref = models.TextField()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_gitremote", "Can manage roles on git remotes"),
        ]


class AnsibleCollectionDeprecated(Content):
    """
    A model that represents if a Collection is `deprecated` for a given RepositoryVersion.
    """

    TYPE = "collection_deprecation"

    namespace = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=64, editable=False)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("namespace", "name")


class AnsibleRepository(Repository, AutoAddObjPermsMixin):
    """
    Repository for "ansible" content.

    Fields:

        last_synced_metadata_time (models.DateTimeField): Last synced metadata time.
        gpgkey (models.TextField): GPG key for verifying signatures.
        private (models.BooleanField): Indicator if this repository is private.

    Relations:
        sistore_signing_service (models.ForeignKey):
            Sigstore service used to sign collections.
        sigstore_verifying_service (models.ForeignKey):
            Sigstore service used to verify collection signatures.
    """

    TYPE = "ansible"
    CONTENT_TYPES = [
        Role,
        CollectionVersion,
        AnsibleCollectionDeprecated,
        CollectionVersionSignature,
        CollectionVersionSigstoreSignature,
        AnsibleNamespaceMetadata,
        CollectionVersionMark,
    ]
    REMOTE_TYPES = [RoleRemote, CollectionRemote, GitRemote]

    last_synced_metadata_time = models.DateTimeField(null=True)
    gpgkey = models.TextField(null=True)
    private = models.BooleanField(default=False)

    sigstore_signing_service = models.ForeignKey(
        SigstoreSigningService,
        on_delete=models.SET_NULL,
        related_name="ansible_repositories",
        null=True,
    )
    sigstore_verifying_service = models.ForeignKey(
        SigstoreVerifyingService,
        on_delete=models.SET_NULL,
        related_name="ansible_repositories",
        null=True,
    )

    @property
    def last_sync_task(self):
        return _get_last_sync_task(self.pk)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

        permissions = [
            ("rebuild_metadata_ansiblerepository", "Can rebuild metadata on the repository"),
            ("repair_ansiblerepository", "Can repair the repository"),
            ("sign_ansiblerepository", "Can sign content on the repository"),
            ("sigstore_sign_ansiblerepository", "Can sign content on the repository with Sigstore"),
            ("sync_ansiblerepository", "Can start a sync task on the repository"),
            ("manage_roles_ansiblerepository", "Can manage roles on repositories"),
            ("modify_ansible_repo_content", "Can modify repository content"),
        ]

    def finalize_new_version(self, new_version):
        """Finalize repo version."""
        removed_collection_versions = new_version.removed(
            base_version=new_version.base_version
        ).filter(pulp_type=CollectionVersion.get_pulp_type())

        # Remove any deprecated, signature, mark and namespace content
        # associated with the removed collection versions
        for version in removed_collection_versions:
            version = version.cast()

            signatures = new_version.get_content(
                content_qs=CollectionVersionSignature.objects.filter(signed_collection=version)
            )
            sigstore_signatures = new_version.get_content(
                content_qs=CollectionVersionSigstoreSignature.objects.filter(
                    signed_collection=version
                )
            )
            new_version.remove_content(signatures)
            new_version.remove_content(sigstore_signatures)

            marks = new_version.get_content(
                content_qs=CollectionVersionMark.objects.filter(marked_collection=version)
            )
            new_version.remove_content(marks)

            other_collection_versions = new_version.get_content(
                content_qs=CollectionVersion.objects.filter(collection=version.collection)
            )

            # AnsibleCollectionDeprecated and Namespace applies to all collection versions in a
            # repository, so only remove it if there are no more collection versions for the
            # specified collection present.
            if not other_collection_versions.exists():
                deprecations = new_version.get_content(
                    content_qs=AnsibleCollectionDeprecated.objects.filter(
                        namespace=version.namespace, name=version.name
                    )
                )
                namespace = new_version.get_content(
                    content_qs=AnsibleNamespaceMetadata.objects.filter(name=version.namespace)
                )

                new_version.remove_content(deprecations)
                new_version.remove_content(namespace)
        remove_duplicates(new_version)
        validate_repo_version(new_version)

        from pulp_ansible.app.tasks.collectionversion_index import update_index

        update_index(repository_version=new_version, is_latest=True)

    @hook(BEFORE_UPDATE, when="remote", has_changed=True)
    def _reset_repository_last_synced_metadata_time(self):
        self.last_synced_metadata_time = None


class AnsibleDistribution(Distribution, AutoAddObjPermsMixin):
    """
    A Distribution for Ansible content.
    """

    TYPE = "ansible"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [("manage_roles_ansibledistribution", "Can manage roles on distributions")]

    @hook(AFTER_CREATE)
    @hook(AFTER_UPDATE)
    @hook(AFTER_DELETE)
    def _update_index(self):
        from pulp_ansible.app.tasks.collectionversion_index import update_distribution_index

        update_distribution_index(self)


class CrossRepositoryCollectionVersionIndex(models.Model):
    """
    A model that indexes all CV content across all repositories.
    """

    repository = models.ForeignKey(AnsibleRepository, on_delete=models.CASCADE)
    repository_version = models.ForeignKey(RepositoryVersion, on_delete=models.CASCADE, null=True)
    collection_version = models.ForeignKey(CollectionVersion, on_delete=models.CASCADE)
    namespace_metadata = models.ForeignKey(
        AnsibleNamespaceMetadata, null=True, on_delete=models.SET_NULL
    )

    is_deprecated = models.BooleanField()
    is_signed = models.BooleanField()
    is_highest = models.BooleanField()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("repository", "repository_version", "collection_version")
