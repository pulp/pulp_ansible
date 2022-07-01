Signature Workflows
===================

``pulp_ansible`` supports Collection signing, syncing, and uploading. Collection signing adds extra
validation when installing Collections with `ansible-galaxy`. Check out the workflows below to see
how to add signature support.

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
