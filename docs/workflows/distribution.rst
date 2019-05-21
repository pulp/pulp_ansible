Publish and Host
================

This section assumes that you have a Repository with content in it. To do this, see the
:doc:`sync`, :doc:`upload-role`, or :doc:`upload-collection` documentation.


Create a Distribution for Repository 'foo'
------------------------------------------

This will distribute the 'latest' RepositoryVersion always which makes it consumable by
``ansible-galaxy`` or ``mazer`` clients. Users create a Distribution which will serve the
RepositoryVersion content at ``$CONTENT_HOST/pulp/content/<distribution.base_path>`` as
demonstrated in the :ref:`ansible-galaxy usage documentation<ansible-galaxy-cli>`.

.. literalinclude:: ../_scripts/distribution_repo.sh
   :language: bash

.. code:: json

    {
        "_href": "/pulp/api/v3/tasks/2610a47e-4e88-4e8c-9d2e-c71734ae7b39/",
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
        "_href": "/pulp/api/v3/tasks/2610a47e-4e88-4e8c-9d2e-c71734ae7b39/",
       ...
    }

.. todo::

    Add link to live API Distribution docs
