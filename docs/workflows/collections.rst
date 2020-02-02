Collection Workflows
====================

Pulp organizes role content into repositories, and you associate the ``ansible-galaxy`` client with
one or more repositories. From a high level you can:

1. :ref:`Create a repo <create-a-collection-repository>`

2. :ref:`Create a distribution <create-distribution-for-collection>` expose that repository at a URL

3. :ref:`Sync content from galaxy.ansible.com <create-collection-remote>`

4. :ref:`Install content from the repo with ansible-galaxy <ansible-galaxy-collections-cli>`


API Client Setup
----------------

To use the bash examples on this page. Run these basic bash utilities below:

.. literalinclude:: ../_scripts/setup.sh
   :language: bash


.. _create-a-collection-repository:

Create a Repository
-------------------

Create a repository and name it the ``foo`` repository.

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

    {
        "pulp_created": "2019-04-29T15:57:59.763712Z",
        "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/",
        "latest_version_href": null,
        "versions_href": "/pulp/api/v3/repositories/ansible/ansible/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/",
        "description": "",
        "name": "foo"
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

.. code:: json

    {
        "pulp_created": "2019-07-26T16:46:23.666410Z",
        "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/4262ed83-e86c-4a13-baff-fc543c46a391/",
        "base_path": "my_content",
        "base_url": "/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "repository": "/pulp/api/v3/repositories/ansible/ansible/301bec4f-c5e7-4a20-a124-f8a1ec1f9229/",
        "repository_version": null
    }


Create a Distribution for a RepositoryVersion (optional)
--------------------------------------------------------

Instead of always distributing the latest RepositoryVersion, you can also specify a specific
RepositoryVersion for a Distribution. This should be used in place of the distribution above, not in
addition to it.

.. literalinclude:: ../_scripts/distribution_repo_version.sh
   :language: bash

.. code:: json

    {
        "pulp_created": "2019-07-26T16:51:04.803014Z",
        "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/c9879338-8656-46aa-a2b2-46fa5d7b0329/",
        "base_path": "my_content",
        "base_url": "/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "repository": null,
        "repository_version": "/pulp/api/v3/repositories/ansible/ansible/301bec4f-c5e7-4a20-a124-f8a1ec1f9229/versions/1/"
    }


.. _create-collection-remote:

Create a CollectionRemote
-------------------------

Creating a CollectionRemote object allows Pulp to sync Collections from an external
content source. This is most commonly is ``https://galaxy.ansible.com/`` or another ``pulp_ansible``
instance.

In this example we will be syncing the Collection with ``namespace=testing``  and ``name=ansible_testing_content``
from ``https://galaxy-dev.ansible.com/api/v2/collections/testing/ansible_testing_content/``.

.. literalinclude:: ../_scripts/remote-collection.sh
   :language: bash

Remote GET Response::

    {
        "pulp_created": "2019-04-29T13:51:10.860792Z",
        "pulp_href": "/pulp/api/v3/remotes/ansible/collection/e1c65074-3a4f-4f06-837e-75a9a90f2c31/",
        "pulp_last_updated": "2019-04-29T13:51:10.860805Z",
        "download_concurrency": 20,
        "name": "bar",
        "policy": "immediate",
        "proxy_url": null,
        "ssl_ca_certificate": null,
        "ssl_client_certificate": null,
        "ssl_client_key": null,
        "ssl_validation": true,
        "url": "https://galaxy-dev.ansible.com/api/v2/collections/testing/ansible_testing_content/",
    }


Sync Repository foo with CollectionRemote
-----------------------------------------

Use the CollectionRemote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch Collection content from the external source.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Repository Version GET Response (when complete)::


    {
        "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/",
        "pulp_created": "2019-05-28T21:51:08.172095Z",
        "number": 1,
        "base_version": null,
        "content_summary": {
            "added": {
                "ansible.collection": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/ansible/collections/?repository_version_added=/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/"
                }
            },
            "removed": {},
            "present": {
                "ansible.collection": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/ansible/collections/?repository_version=/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/"
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

Install your role by name by specifying the distribution serving your Repository's content using the
``-s`` option.

``ansible-galaxy collection install testing.ansible_testing_content:4.0.6 -c -s http://localhost/pulp_ansible/galaxy/my_content/``


Configuring ansible-galaxy
~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the `ansible-galaxy config files <https://docs.ansible.com/ansible/latest/user_guide/
collections_using.html#configuring-the-ansible-galaxy-client>`_ to specify the distribution
``ansible-galaxy`` should interact with. To use this, set up your distribution in your ansible
config (e.g. ``~/.ansible.cfg`` or ``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server: http://localhost/pulp_ansible/galaxy/my_content/

Then you can install without the ``-s`` url

.. code::

   ansible-galaxy collection install testing.ansible_testing_content:4.0.6

   - downloading role 'elasticsearch', owned by elastic
   - downloading role from http://localhost/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
   - extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
   - elastic.elasticsearch (6.2.4) was installed successfully


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
    ansible-galaxy collection publish namespace_name-collection_name-1.0.0.tar.gz -c -s http://localhost:24817/pulp_ansible/galaxy/my_content/

The client upload the Collection to the Repository associated with the Distribution. Each upload
creates a new Repository Version for the Repository.


Add/Remove Content to a Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whether your Role was fetched with a sync or uploaded, any content can also be added/removed to a
repository manually::

    http POST localhost/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/modify/ \
        add_content_units:="['/pulp/api/v3/content/ansible/collections/d2bab58c-50f2-4f1d-9cf0-8ceb1680f31b/']"


This is entirely implemented by `pulpcore`, please see their reference docs for more information.
