pulp_ansible
============

.. figure:: https://github.com/pulp/pulp_ansible/workflows/Pulp%20CI/badge.svg
   :alt: Pulp CI

A Pulp plugin to support hosting ``Role`` and ``Collection`` Ansible content.

For more information, please see the `documentation <https://docs.pulpproject.org/pulp_ansible/>`_.


Collection Support
------------------

.. warning::

    The 'Collection' content type is currently in tech-preview. Breaking changes could be introduced
    in the future.

pulp_ansible can manage the `multi-role repository content <https://galaxy.ansible.com/docs/using/
installing.html#multi-role-repositories>`_ referred to as a `Collection`. The following features are
supported:

* `ansible-galaxy collection publish` - Upload a Collection to pulp_ansible for association with one or more
  repositories.
* `ansible-galaxy collection install` - Install a Collection from pulp_ansible.


Configuring Collection Support
------------------------------

You'll have to specify the protocol and hostname the pulp_ansible REST API is being served on. For
pulp_ansible to interact with `ansible-galaxy` correctly it needs the entire hostname. This is done
using the `ANSIBLE_HOSTNAME` setting in Pulp. For example if its serving with http on localhost it
would be::

    export PULP_ANSIBLE_API_HOSTNAME='http://localhost:24817'
    export PULP_ANSIBLE_CONTENT_HOSTNAME='http://localhost:24816/pulp/content'

or in your systemd environment::

    Environment="PULP_ANSIBLE_API_HOSTNAME=http://localhost:24817"
    Environment="PULP_ANSIBLE_CONTENT_HOSTNAME=http://localhost:24816/pulp/content"


How to File an Issue
--------------------

`New pulp_ansible issue <https://pulp.plan.io/projects/ansible_plugin/issues/new>`_.

.. warning::
  Is this security related? If so, please follow the `Security Disclosures <https://docs.pulpproject.org/pulpcore/bugs-features.html#security-bugs>`_ procedure.

Please set **only the fields in this table**. See `Redmine Fields <https://docs.pulpproject.org/pulpcore/bugs-features.html#redmine-fields>`_ for more detailed
descriptions of all the fields and how they are used.

.. list-table::
   :header-rows: 1
   :widths: auto
   :align: center

   * - Field
     - Instructions

   * - Tracker
     - For a bug, select ``Issue``, for a feature-request, choose ``Story``,
       for a backport request, choose ``Backport``.

   * - Subject
     - Strive to be specific and concise.

   * - Description
     - This is the most important part! Please see `Description Field <https://docs.pulpproject.org/pulpcore/bugs-features.html#issue-description>`_.

   * - Category
     - Choose one if applicable, blank is OK.

   * - Version
     - The version of pulp_ansible that you discovered the issue.

   * - OS
     - Please select your operating system.

   * - Tags
     - For searching. Select 0 or many, best judgement.
       If an issue requires a functional test. Add the tag `Functional test`.
