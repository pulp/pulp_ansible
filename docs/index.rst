Welcome to Pulp Ansible's documentation!
========================================

Use ``pulp_ansible`` to create a private Galaxy. It doesn't have a UI currently, but using an API
you can:

* Mirror a subset of roles on-premise
* Mirror all of Galaxy’s roles on-premise
* Store private Ansible roles on-premise
* Install Roles from pulp_ansible using the `ansible-galaxy` CLI
* Version Role content over time and rollback if necessary
* Support for the new multi-role content type from Galaxy

Issues are tracked `in Redmine <https://pulp.plan.io/projects/ansible_plugin/issues>`_. You can file
a new issue or feature request `here <https://pulp.plan.io/projects/ansible_plugin/issues/new>`_.
You can also ask questions in the #pulp-ansible channel on
`Freenode <https://webchat.freenode.net/>`_.


Table of Contents
-----------------

.. toctree::
   :maxdepth: 1

   installation
   workflows/index
   restapi
   bindings
   settings
   contributing
   changes


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
