
.. note::

    To use these examples you will need to install ``httpie`` to make requests and ``jq`` to parse
    responses. ``httpie`` has ``netrc`` support so each request submits Basic Authentication with
    it. For Pulp's defaults the ``.netrc`` would have the following configuration:

    .. code-block:: bash

        machine localhost
        login admin
        password admin

.. note::

    To make these workflows copy/paste-able, we make use of environment variables. The first
    variable to set is the hostname and port::

       export BASE_ADDR=http://<hostname>:24817


Role Workflows
==============

.. toctree::
   :maxdepth: 2

   sync
   upload-role
   add-remove
   distribution
   ansible-galaxy-client


Collection Workflows
====================

This section documents the `Collection` capabilities of ``pulp_ansible`` in a "quickstart" style
along with the ``mazer`` client.


.. toctree::
   :maxdepth: 2

   sync-collection
   upload-collection
   add-remove
   distribution
   mazer-client
