Role Workflows
==============

Pulp organizes role content into repositories, and you associate the ``ansible-galaxy`` client with
one or more repositories. From a high level you can:

1. :ref:`Create a repo <create-a-roles-repository>`

2. :ref:`Create a distribution <create-distribution-for-repo>` expose that repository at a URL

3. :ref:`Sync content from galaxy.ansible.com <create-role-remote>`

4. :ref:`Install content from the repo with ansible-galaxy <ansible-galaxy-roles-cli>`


API Client Setup
----------------

To use the bash examples on this page. Run these basic bash utilities below:

.. literalinclude:: ../_scripts/setup.sh
   :language: bash


.. _create-a-roles-repository:

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


.. _create-distribution-for-repo:

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


.. _create-role-remote:

Create a Remote
---------------

Creating a Remote object informs Pulp about an external content source, which most commonly is
``https://galaxy.ansible.com/`` or another ``pulp_ansible`` instance. In this case, we will be
syncing all Roles where ``namespace=elastic`` on Galaxy. You can browse those Roles Pulp will import
`here <https://galaxy.ansible.com/api/v1/roles/?namespace=elastic>`_.

.. literalinclude:: ../_scripts/remote.sh
   :language: bash

Remote GET Response::

    {
        "pulp_href": "/pulp/api/v3/remotes/ansible/ansible/e1c65074-3a4f-4f06-837e-75a9a90f2c31/",
    }


.. _role-sync-with-remote:

Sync Repository foo with Remote
-------------------------------

Use the Remote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch content from the Remote and add to the Repository.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Repository Version GET Response (when complete)::

  {
      "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/",
      "base_version": null,
      "content_summary": {
          "added": {
              "ansible.role": {
                  "count": 16,
                  "href": "/pulp/api/v3/content/ansible/roles/?repository_version_added=/pulp/api/v3/repositories/ansible/ansible/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/"
              }
          },
          "present": {
              "ansible.role": {
                  "count": 16,
                  "href": "/pulp/api/v3/content/ansible/roles/?repository_version=/pulp/api/v3/repositories/ansible/ansible/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/"
              }
          },
          "removed": {}
      },
      "number": 1
  }


Reference (pulpcore): `Repository Version List API Usage <https://docs.pulpproject.org/
restapi.html#operation/repositories_versions_list>`_


.. _ansible-galaxy-roles-cli:

Install a Role, hosted by Pulp, using ``ansible-galaxy``
--------------------------------------------------------

Using a direct path
~~~~~~~~~~~~~~~~~~~

Install your role by name by specifying the distribution serving your Repository's content using the
``-s`` option.

``ansible-galaxy install elasticsearch,6.2.4 -c -s http://pulp.example.com/pulp_ansible/galaxy/my_content/``


Configuring ansible-galaxy Permanently
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the `ansible-galaxy config files <https://docs.ansible.com/ansible/latest/cli/
ansible-galaxy.html#environment>`_ to specify the distribution ``ansible-galaxy`` should interact
with. To use this, set up your distribution in your ansible config (e.g. ``~/.ansible.cfg`` or
``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server: http://pulp.example.com/pulp_ansible/galaxy/my_content/

Then you can install without the ``-s`` url

.. code::

   $ ansible-galaxy install elastic.elasticsearch,6.2.4
   - downloading role 'elasticsearch', owned by elastic
   - downloading role from http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
   - extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
   - elastic.elasticsearch (6.2.4) was installed successfully


.. _roles-add-remove:

Add/Remove Content to a Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whether your Role was fetched with a sync or uploaded, any content can also be added/removed to a
repository manually::

    http POST pulp.example.com/pulp/api/v3/repositories/ansible/ansible/modify/ \
        add_content_units:="['/pulp/api/v3/content/ansible/roles/d2bab58c-50f2-4f1d-9cf0-8ceb1680f31b/']"


This is entirely implemented by `pulpcore`, please see their reference docs for more information.

Reference (pulpcore): `Repository Version Creation API Usage
<https://docs.pulpproject.org/restapi.html#operation/repositories_versions_create>`_
