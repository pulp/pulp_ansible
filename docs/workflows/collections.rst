Collection Workflows
====================

Pulp organizes role content into repositories, and you associate the ``ansible-galaxy`` client with
one or more repositories. From a high level you can:

1. :ref:`Create a repo <create-a-collection-repository>`

2. :ref:`Create a distribution <create-distribution-for-collection>` expose that repository at a URL

3. :ref:`Sync content from galaxy.ansible.com <create-collection-remote>`

4. :ref:`Install content from the repo with ansible-galaxy <ansible-galaxy-collections-cli>`


Pulp-CLI Setup
----------------

To use the example commands on this page, install the Pulp-CLI as shown below.

.. literalinclude:: ../_scripts/setup.sh
   :language: bash


.. _create-a-collection-repository:

Create a Repository
-------------------

Create a repository and name it the ``foo`` repository.

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository create output::

    {
      "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/",
      "pulp_created": "2021-01-26T22:48:11.479496Z",
      "versions_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/",
      "latest_version_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/0/",
      "name": "foo",
      "description": null,
      "remote": null
    }

Reference (pulpcore): `Repository API Usage <https://docs.pulpproject.org/restapi.html#tag/
repositories>`_



.. _create-distribution-for-collection:

Create a Distribution for Repository 'foo'
------------------------------------------

This will make the latest Repository Version content available for ``ansible-galaxy` clients. Each
distribution names the url it can be accessed from on an attribute called ``client_url``. The
``client_url`` can be used with the ``ansible-galaxy`` client with the ``-s`` option. See the
:ref:`ansible-galaxy-roles-cli` docs for more details.

For example a distribution with ``base_path`` set to ``my_content`` could have a URL like::

    http://pulp.example.com/pulp_ansible/galaxy/my_content/


.. literalinclude:: ../_scripts/distribution_repo.sh
   :language: bash

Distribution create output::

    Started background task /pulp/api/v3/tasks/48d187f6-d1d0-4d83-b803-dae9fe976da9/
    .Done.
    {
      "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/148ce745-3dd5-4dda-a0ba-f9c5ec7119e1/",
      "pulp_created": "2021-01-26T22:51:34.380612Z",
      "base_path": "my_content",
      "content_guard": null,
      "name": "baz",
      "repository": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/",
      "repository_version": null,
      "client_url": "http://pulp3-source-fedora31.localhost.example.com/pulp_ansible/galaxy/my_content/"
    }

Create a Distribution for a RepositoryVersion (optional)
--------------------------------------------------------

Instead of always distributing the latest RepositoryVersion, you can also specify a specific
RepositoryVersion for a Distribution. This should be used in place of the distribution above, not in
addition to it.

.. literalinclude:: ../_scripts/distribution_repo_version.sh
   :language: bash

Distribution create output::

    Started background task /pulp/api/v3/tasks/48d187f6-d1d0-4d83-b803-dae9fe976da9/
    .Done.
    {
      "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/148ce745-3dd5-4dda-a0ba-f9c5ec7119e1/",
      "pulp_created": "2021-01-26T22:51:34.380612Z",
      "base_path": "my_content",
      "content_guard": null,
      "name": "baz",
      "repository": null,
      "repository_version": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/",
      "client_url": "http://pulp3-source-fedora31.localhost.example.com/pulp_ansible/galaxy/my_content/"
    }

.. _create-collection-remote:

Create a CollectionRemote
-------------------------

Creating a CollectionRemote object allows Pulp to sync Collections from an external
content source. This is most commonly is ``https://galaxy.ansible.com/`` or another ``pulp_ansible``
instance.

In this example we will be syncing the Collection with ``namespace=testing``  and ``name=ansible_testing_content``
from ``https://galaxy-dev.ansible.com/``.

.. literalinclude:: ../_scripts/remote-collection.sh
   :language: bash

Remote create output::

    {
      "pulp_href": "/pulp/api/v3/remotes/ansible/collection/80ba27e3-b4d6-4ddb-9677-9e40c04352ef/",
      "pulp_created": "2021-01-26T23:16:06.790367Z",
      "name": "cbar",
      "url": "https://galaxy-dev.ansible.com/",
      "ca_cert": null,
      "client_cert": null,
      "client_key": null,
      "tls_validation": true,
      "proxy_url": null,
      "username": null,
      "password": null,
      "pulp_last_updated": "2021-01-26T23:16:06.790390Z",
      "download_concurrency": 10,
      "policy": "immediate",
      "total_timeout": null,
      "connect_timeout": null,
      "sock_connect_timeout": null,
      "sock_read_timeout": null,
      "requirements_file": "collections:\n  - testing.ansible_testing_content",
      "auth_url": null,
      "token": null,
      "rate_limit": null
    }

For `remote sources that require authentication <https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#configuring-the-ansible-galaxy-client>`_, tokens can be used. You can provide the ``token``
and/or ``auth_url``.

In this example we will be syncing the Collection with ``namespace=testing``  and ``name=ansible_testing_content``
from ``https://cloud.redhat.com/api/automation-hub/v3/collections/testing/ansible_testing_content``.

.. literalinclude:: ../_scripts/remote-collection-token.sh
   :language: bash

Remote create output::

    {
      "pulp_href": "/pulp/api/v3/remotes/ansible/collection/80ba27e3-b4d6-4ddb-9677-9e40c04352ef/",
      "pulp_created": "2021-01-26T23:16:06.790367Z",
      "name": "abar",
      "url": "https://cloud.redhat.com/api/automation-hub/",
      "ca_cert": null,
      "client_cert": null,
      "client_key": null,
      "tls_validation": false,
      "proxy_url": null,
      "username": null,
      "password": null,
      "pulp_last_updated": "2021-01-26T23:16:06.790390Z",
      "download_concurrency": 10,
      "policy": "immediate",
      "total_timeout": null,
      "connect_timeout": null,
      "sock_connect_timeout": null,
      "sock_read_timeout": null,
      "requirements_file": "collections:\n  - testing.ansible_testing_content",
      "auth_url": "https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token",
      "token": "$ANSIBLE_TOKEN_AUTH",
      "rate_limit": null
    }

Sync Repository foo with CollectionRemote
-----------------------------------------

Use the CollectionRemote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch Collection content from the external source.

.. literalinclude:: ../_scripts/sync-collection.sh
   :language: bash

Repository Version GET Response (when complete)::


    {
      "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/",
      "pulp_created": "2021-01-26T23:25:06.473972Z",
      "number": 1,
      "base_version": null,
      "content_summary": {
        "added": {
          "ansible.collection_version": {
            "count": 2,
            "href": "/pulp/api/v3/content/ansible/collection_versions/?repository_version_added=/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/"
          }
        },
        "removed": {},
        "present": {
          "ansible.collection_version": {
            "count": 2,
            "href": "/pulp/api/v3/content/ansible/collection_versions/?repository_version=/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/"
          }
        }
      }
    }



.. _ansible-galaxy-collections-cli:

Install a Collection, hosted by Pulp, using ``ansible-galaxy``
--------------------------------------------------------------

You can use `ansible-galaxy` to install a collection by its namespace and name from pulp_ansible
using the `install` command. For example to install the `hello` collection from above into a
directory `~/collections` you can specify:

``ansible-galaxy collection install testing.ansible_testing_content -c -s http://localhost/pulp_ansible/galaxy/my_content/``


This assumes that the `hello` Collection is being served by the Distribution `ansible-galaxy` is
configured to use.

Using a specific version
~~~~~~~~~~~~~~~~~~~~~~~~

Install your collection by name by specifying the distribution serving your Repository's content using the
``-s`` option.

``ansible-galaxy collection install testing.ansible_testing_content:4.0.6 -c -s http://localhost/pulp_ansible/galaxy/my_content/``

Note: the ``-c`` flag tells ``ansible-galaxy`` to ignore self signed https certificates.

Configuring ansible-galaxy
~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the `ansible-galaxy config files <https://docs.ansible.com/ansible/latest/user_guide/
collections_using.html#configuring-the-ansible-galaxy-client>`_ to specify the distribution
``ansible-galaxy`` should interact with. To use this, set up your distribution in your ansible
config (e.g. ``~/.ansible.cfg`` or ``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server_list = pulp, my_fallback_server

    [galaxy_server.pulp]
    url = http://localhost/pulp_ansible/galaxy/my_content/

    [galaxy_server.my_fallback_server]
    url = http://localhost/pulp_ansible/galaxy/my_other_content/
    username = my_user
    password = my_password

    [galaxy_server.deprecated]
    url = http://localhost/pulp_ansible/galaxy/deprecated/
    username = my_user
    password = my_password

Servers will be used in the order that they appear in ``server_list`` in the configuration file. Specific servers 
can also be specified using the ``-s`` (or ``--server``) flag, either by their name or URL. In this example
``ansible-galaxy`` will attempt to fetch content from ``pulp`` and fallback to ``my_fallback_server`` if it can't
find anything. The ``deprecated`` server is not listed under ``server_list``, so ``ansible-galaxy`` won't pull
content from it unless the server is specified explicitly with the ``-s`` flag.

.. code::

   # Downloads from the "pulp" server
   ansible-galaxy collection install testing.ansible_testing_content:4.0.6

   # Downloads from the "deprecated" server
   ansible-galaxy collection install testing.ansible_testing_content:4.0.6 -s deprecated


.. _collection-publish:

Publish (Upload) a Collection
-----------------------------

You can use `ansible-galaxy` to publish any `built artifact <https://docs.ansible.com/ansible/
latest/dev_guide/developing_collections.html#building-collections>`_ to pulp_ansible by running::

    ansible-galaxy collection build  # from inside the root directory of the collection
    ansible-galaxy collection publish path/to/artifact.tar.gz

For example if you have ansible-galaxy installed and configured the script below will upload a
Collection to pulp_ansible and display it::

    ansible-galaxy collection init namespace_name.collection_name
    ansible-galaxy collection build namespace_name/collection_name/
    ansible-galaxy collection publish namespace_name-collection_name-1.0.0.tar.gz -c

The client upload the Collection to the Repository associated with the Distribution. Each upload
creates a new Repository Version for the Repository.
