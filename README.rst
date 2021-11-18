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

`New pulp_ansible issue <https://github.com/pulp/pulp_ansible/issues/new>`_.

.. warning::
  Is this security related? If so, please follow the `Security Disclosures <https://docs.pulpproject.org/pulpcore/bugs-features.html#security-bugs>`_ procedure.
