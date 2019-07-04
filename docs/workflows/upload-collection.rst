Upload Content
==============

Upload a Collection via the REST API
------------------------------------

A collection tarball can be uploaded via the REST API and the server determines the metadata and
creates the Collection model.

Suppose you have a file locally named collection.tgz you can upload that to ``pulp_ansible`` with::

    http --form POST :24817/ansible/collections/ file@collection.tgz


An optional ``sha256`` digest can be passed and is expected to be the sha256 digest of the tarball
being uploaded. Assume a sha256 of
``35281bc21343d60f865a091ecc97e28e362c47a52bb6edd6ffd279f94f4ccb0d`` you would upload this with::

    http --form POST :24817/ansible/collections/ file@collection.tgz sha256=35281bc21343d60f865a091ecc97e28e362c47a52bb6edd6ffd279f94f4ccb0d


Upload a Collection via 'mazer'
-------------------------------

See the :ref:`mazer-publish` documentation on how to us ``mazer publish`` to publish Collections to
``pulp_ansible``.


Add Content to a Repository
---------------------------

See :ref:`add-remove`
