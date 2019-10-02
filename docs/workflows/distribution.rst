Publish and Host
================

This section assumes that you have a Repository with content in it. To do this, see the
:doc:`sync`, :doc:`upload-role`, or :doc:`upload-collection` documentation.


Create a Distribution for Repository 'foo'
------------------------------------------

This will distribute the 'latest' RepositoryVersion always which makes it consumable by
``ansible-galaxy`` client. Users create a Distribution which will serve the RepositoryVersion
content at ``$CONTENT_HOST/pulp/content/<distribution.base_path>`` as demonstrated in the
:ref:`ansible-galaxy usage documentation<ansible-galaxy-cli>`.

.. literalinclude:: ../_scripts/distribution_repo.sh
   :language: bash

.. code:: json

    {
        "pulp_created": "2019-07-26T16:46:23.666410Z",
        "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/4262ed83-e86c-4a13-baff-fc543c46a391/",
        "base_path": "foo",
        "base_url": "/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "repository": "/pulp/api/v3/repositories/301bec4f-c5e7-4a20-a124-f8a1ec1f9229/",
        "repository_version": null
    }

.. todo::

    Add link to live API Distribution docs


Create a Distribution for a RepositoryVersion
---------------------------------------------

Instead of always distributing the latest RepositoryVersion, you can also specify a specific
RepositoryVersion for a Distribution.

.. literalinclude:: ../_scripts/distribution_repo_version.sh
   :language: bash

.. code:: json

    {
        "pulp_created": "2019-07-26T16:51:04.803014Z",
        "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/c9879338-8656-46aa-a2b2-46fa5d7b0329/",
        "base_path": "foo",
        "base_url": "/pulp/content/foo",
        "content_guard": null,
        "name": "baz",
        "repository": null,
        "repository_version": "/pulp/api/v3/repositories/301bec4f-c5e7-4a20-a124-f8a1ec1f9229/versions/1/"
    }

.. todo::

    Add link to live API Distribution docs
