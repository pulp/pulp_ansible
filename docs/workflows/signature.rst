Signature Workflows
===================

``pulp_ansible`` supports Collection signing, syncing, and uploading. Collection signing adds extra
validation when installing Collections with `ansible-galaxy`. Check out the workflows below to see
how to add signature support.


-----------
GPG Signing
-----------

Setup
-----
In order to verify signature validity on uploads you will need to store your trusted key on the
repositories ``gpgkey`` attribute.

.. note::
   You can upload signatures without supplying Pulp any key, but ``pulp_ansible`` will not
   perform validity checks on the uploaded signature. You will also have to configure the
   ``ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION`` setting to ``False``. By default and once a key is
   provided, all signatures impossible to verify are rejected.

In order to have ``pulp_ansible`` sign collections stored in your repositories you will need to set
up a signing service. First, create/import the key you intend to sign your collections with onto
your Pulp system. Second, create a signing script on your Pulp system with the parameters you want
on the generated signatures. Galaxy uses a signing script like the one below:

.. code-block:: bash

    #!/usr/bin/env bash
    FILE_PATH=$1
    SIGNATURE_PATH="$1.asc"

    # Create a detached signature
    gpg --quiet --batch --homedir ~/.gnupg/ --detach-sign --local-user "${PULP_SIGNING_KEY_FINGERPRINT}" \
        --armor --output ${SIGNATURE_PATH} ${FILE_PATH}

    # Check the exit status
    STATUS=$?
    if [[ ${STATUS} -eq 0 ]]; then
       echo {\"file\": \"${FILE_PATH}\", \"signature\": \"${SIGNATURE_PATH}\"}
    else
       exit ${STATUS}
    fi

Third, create the signing service using ``pulpcore-manager``:

.. code-block:: bash

    pulpcore-manager add-signing-service ansible-signing-service $SCRIPT_LOCATION $PUBKEY_FINGERPRINT

Reference: `Signing Service <https://docs.pulpproject.org/pulpcore/workflows/signed-metadata.html>`_

Signing Collections
-------------------

Sign collections stored in repository ``foo`` with the signing service ``ansible-signing-service``:

.. code-block:: bash

    pulp ansible repository sign --name foo --signing-service ansible-signing-service

By default it will sign everything in the repository, specify ``--content-units`` with a list of
specific collection hrefs you want to sign. Collections can have multiple signatures attached to
them in a repository as long as they are all from different keys.

Syncing Signed Collections
--------------------------

Signature information will be present in the Galaxy APIs if your repository has signatures in it
and when syncing from a Galaxy repository, signatures will automatically be synced as well if
present. You can also specify to only sync Collections that have signatures with the
``signed_only`` field on the remote. e.g.:

.. code-block:: bash

    pulp ansible remote update --name foo --signed-only
    # Sync task will only sync collections with signatures now
    pulp ansible repository sync --name foo --remote foo

Uploading Signed Collections
----------------------------

Signatures can also be manually created and uploaded to ``pulp_ansible``.

.. code-block:: bash

    pulp ansible content -t signature upload --file $SIGNATURE --collection $COLLECTION_HREF

Signatures can be verified upon upload by setting the ``keyring`` field on the repository to your
keyring location, and then specifying the ``repository`` option when uploading the signature.

.. code-block:: bash

    pulp ansible repository update --name foo --keyring $KEYRING_FILE_LOCATION
    # Validate signature against keyring of repository
    pulp ansible content -t signature upload --file $SIGNATURE --collection $COLLECTION_HREF --repository foo

Verifying Signatures with ``ansible-galaxy``
--------------------------------------------

Installing collections from ``pulp_ansible`` with signatures via `ansible-galaxy` requires
specifying the keyring to perform the validation upon install:

.. code-block:: bash

    ansible-galaxy collection install $COLLECTION -s "$BASE_ADDR"pulp_ansible/galaxy/foo/api/ --keyring $KEYRING_FILE_LOCATION

You can also verify already installed collections with the verify command:

.. code-block:: bash

    ansible-galaxy collection verify $COLLECTION -s "$BASE_ADDR"pulp_ansible/galaxy/foo/api/ --keyring $KEYRING_FILE_LOCATION


----------------
Sigstore Signing
----------------

About Sigstore
--------------

`Sigstore <https://www.sigstore.dev/>`__
is a new standard for protecting software that simplifies the signing process for digital artifacts.
``pulp_ansible`` supports generating and verifying Sigstore signatures for Ansible collections.

**How does Sigstore work?**
Sigstore makes use of three different components to generate and verify signatures:

- `Rekor <https://docs.sigstore.dev/rekor/overview/>`__
is Sigstore's Transparency Log, an immutable and tamper-resistant ledger used to log signatures and their metadata.

- `Fulcio <https://docs.sigstore.dev/fulcio/overview/>`__
is a free Certificate Authority used to generate ephemeral signing certificates for artifacts.

- `Cosign https://docs.sigstore.dev/cosign/overview/`__
is the command line client used to sign and verify artifacts. The same functionalities are also handled by Sigstore client libraries, such as `sigstore-python <https://github.com/sigstore/sigstore-python>`__.

Setting up Sigstore in Pulp
---------------------------

============================
Configuring Sigstore signing
============================

To sign collections in a ``pulp_ansible`` repository, Sigstore needs to be configured by a Pulp admin via the creation of a Sigstore Signing Service.
This can be done with the Pulp admin CLI that takes a JSON configuration file as input, or by manually specifying configuration entries with command line arguments.
In the case where both a file and command line arguments are passed to the CLI, arguments override corresponding entries in the configuration file.

Here is an example of configuration file:

.. code-block:: json

    {
        "name": "my-signing-service",
        "rekor-url": "https://rekor.sigstore.dev",
        "rekor-root-pubkey": "-----BEGIN PUBLIC KEY----- MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMMgqllG63h1hb313Gu16zCu1ctcZ j9Wi6b+xM2p2Ofv3A4I4E5/pgGjlGRAd8G8aQrq3HwCT//3TERROMVc84w== -----END PUBLIC KEY-----",
        "fulcio-url": "https://fulcio.sigstore.dev",
        "tuf-url": "https://sigstore-tuf-root.storage.googleapis.com/",
        "oidc-issuer": "https://oauth2.sigstore.dev/auth",
        "ctfe-pubkey": "-----BEGIN PUBLIC KEY----- MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEgL0oW2gouGy8n90I0JuAKD1tfiw4 B3rDKtWDuV6/oWkPb9u0/9CbDfdWqedgFsDIWaHu4PFfrkws7CX9ByHpJw== -----END PUBLIC KEY-----",
    }


List of Sigstore configuration parameters:

- name: Name of the Sigstore signing service, acting as a unique identifier.
- rekor-url: The URL of the Rekor instance to use for logging signatures. Defaults to the Rekor public good instance URL (https://rekor.sigstore.dev).
- rekor_root_pubkey: A PEM-encoded root public key for Rekor itself.
- fulcio_url: The URL of the Fulcio instance to use for getting signing certificates. Defaults to the Fulcio public good instance URL (https://fulcio.sigstore.dev).
- tuf_url: The URL of the TUF metadata repository instance to use. Defaults to the public TUF instance URL (https://sigstore-tuf-root.storage.googleapis.com/).
- oidc_issuer: The OpenID Connect issuer to use for signing. Defaults to the public OAuth2 server URL (https://oauth2.sigstore.dev/auth).
- oidc_client_secret: The encrypted OIDC client secret to authentify to Sigstore.
- ctfe_pubkey: A PEM-encoded public key for the CT log.

**Important note:** The URLs for Fulcio, Rekor and TUF all default to the Sigstore public instances.
Using one of those instances for logging signatures or generating certificates means that information such as corporate emails or identities will be visible to the public.
Once this information is entered in the logs, it is impossible to remove or alter it.

Example use:

.. code-block:: bash
    pulpcore-manager add-sigstore-signing-service --from-file sigstore-signing-config.json --oidc-client-secret="p6Hisft9nWQ1FdPExampleSecret"

Pulp admins can also remove Sigstore signing services configured:

.. code-block:: bash
    pulpcore-manager remove-sigstore-signing-service my-signing-service

===========================================
Configuring Sigstore signature verification
===========================================

In the same way, Pulp admins can configure Sigstore verifying services for checking the validity of signatures on upload in a repository.

Here is an example configuration file:

.. code-block:: json

    {
        "name": "my-verifying-service",
        "rekor-url": "https://rekor.sigstore.dev",
        "rekor-root-pubkey": "-----BEGIN PUBLIC KEY----- MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEMMgqllG63h1hb313Gu16zCu1ctcZ j9Wi6b+xM2p2Ofv3A4I4E5/pgGjlGRAd8G8aQrq3HwCT//3TERROMVc84w== -----END PUBLIC KEY-----",
        "tuf-url": "https://sigstore-tuf-root.storage.googleapis.com/",
        "certificate-chain": "-----BEGIN CERTIFICATE----- MIICFzCCAb2gAwIBAgIUTlC6Sec7aMzNSEPjM4GGRGD4SRQwCgYIKoZIzj0EAwIw aDEMMAoGA1UEBhMDVVNBMQswCQYDVQQIEwJXQTERMA8GA1UEBxMIS2lya2xhbmQx FTATBgNVBAkTDDc2NyA2dGggU3QgUzEOMAwGA1UEERMFOTgwMzMxETAPBgNVBAoT CHNpZ3N0b3JlMB4XDTIzMDQxOTA5MjAwNFoXDTMzMDQxOTA5MjAwNFowaDEMMAoG A1UEBhMDVVNBMQswCQYDVQQIEwJXQTERMA8GA1UEBxMIS2lya2xhbmQxFTATBgNV BAkTDDc2NyA2dGggU3QgUzEOMAwGA1UEERMFOTgwMzMxETAPBgNVBAoTCHNpZ3N0 b3JlMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEpUO2LlVYeoWPImhoiqWZ//ou 6moSKSWV81ao6FdWXPPLNf1We//hljTVSMTecy9nXrs6l37tyW9PZ4PCh3uBWKNF MEMwDgYDVR0PAQH/BAQDAgEGMBIGA1UdEwEB/wQIMAYBAf8CAQEwHQYDVR0OBBYE FBKveBwpxVN+GGVl4lYhtGf9JwlxMAoGCCqGSM49BAMCA0gAMEUCID/2LldMDc0M UoGRusZhP5WMuUXtQ+lMivTYbZiDNAavAiEAwt4NSqNkYPwMdBU9GiU2v/6jxzUs AvuFGeDHHbe+K2Y= -----END CERTIFICATE-----"
        "expected-identity": "user@example.com",
        "expected-oidc-issuer": "https://oauth2.sigstore.dev/auth",
        "verify-offline": false
    }


List of Sigstore configuration parameters:

- name: Name of the Sigstore verifying service
- rekor-url: The URL of the Rekor instance to use for checking signature logs. Defaults to the Rekor public good instance URL (https://rekor.sigstore.dev).
- rekor-root-pubkey: A PEM-encoded root public key for Rekor itself.
- tuf-url: The URL of the TUF metadata repository instance to use. Defaults to the public TUF instance URL (https://sigstore-tuf-root.storage.googleapis.com/).
- certificate-chain: A list of PEM-encoded CA certificates needed to build the Fulcio signing certificate chain. Defaults to None.
- expected-oidc-issuer: The expected OIDC issuer in the signing certificate.
- expected-identity: The expected identity in the signing certificate.
- verify-offline: Verify the signature offline. Needs the presence of a Sigstore bundle in the verification materials.

Example use:

.. code-block:: bash
    pulpcore-manager add-sigstore-verifying-service --from-file sigstore-verifying-config.json

Pulp admins can also remove Sigstore verifying services configured:

.. code-block:: bash
    pulpcore-manager remove-sigstore-verifying-service my-verifying-service


Signing Collections with Sigstore
---------------------------------

Pulp users can use one of the Sigstore signing services to sign collections and upload the resulting signature materials to a repository.
Sigstore signature materials consist of:

- A manifest ``.ansible-sign/sha256sum/txt`` containing the checksums of all files present in the collection
- A `Sigstore bundle <https://docs.sigstore.dev/signing/quickstart/#signing-a-blob>`__ ``.ansible-sign/sha256sum/txt.sigstore`` used for verification

With the ``pulp`` CLI:

.. code-block:: bash
    pulp ansible repository sign --name foo --signing-service my-signing-service


Similarly to the GPG signing flow, specify ``--content-units`` with a list of
specific collection hrefs you want to sign. By default, all the collections in the repository will be signed.


Uploading Sigstore signatures for a collection
----------------------------------------------

Signatures can also be manually created and uploaded to ``pulp_ansible``.

.. code-block:: bash

    pulp ansible content -t sigstore-signature upload --bundle sha256sum.txt.sigstore --collection $COLLECTION_HREF

Signatures are verified upon upload by a Sigstore verifying service set up for the repository.


When a new collection version is uploaded to a repository, if a Sigstore bundle and the signed checksums manifest are present under an ``.ansible-sign/`` directory,
the signature will be extracted and verified against all the Sigstore verifying services configured on the given repository.
If at least one verifying service was able to validate the signature, it will be validated and uploaded as a collection version Sigstore signature
associated with the collection version.
