Synchronize Roles from Galaxy
=============================

Users can populate their repositories with content from an external source like Galaxy by syncing
their Repository.

Create a Repository
-------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

    {
        "pulp_created": "2019-04-29T15:57:59.763712Z",
        "pulp_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/",
        "_latest_version_href": null,
        "_versions_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/",
        "description": "",
        "name": "foo"
    }

Reference (pulpcore): `Repository API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#tag/repositories>`_


Create a Remote
---------------

Creating a Remote object informs Pulp about an external content source, which most commonly is
``https://galaxy.ansible.com/`` or another ``pulp_ansible`` instance. In this case, we will be
syncing all Roles where ``namespace=elastic`` on Galaxy. You can see those Roles
`here <https://galaxy.ansible.com/api/v1/roles/?namespace=elastic>`_.

.. literalinclude:: ../_scripts/remote.sh
   :language: bash

Remote GET Response::

    {
        "pulp_href": "/pulp/api/v3/remotes/ansible/ansible/e1c65074-3a4f-4f06-837e-75a9a90f2c31/",
    }

.. todo::

    Add a reference link to the live API


Sync Repository foo with Remote
-------------------------------

Use the Remote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch content from the Remote and add to the Repository.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Repository Version GET Response (when complete)::

  {
      "pulp_href": "/pulp/api/v3/repositories/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/",
      "base_version": null,
      "content_summary": {
          "added": {
              "ansible.role": {
                  "count": 16,
                  "href": "/pulp/api/v3/content/ansible/roles/?repository_version_added=/pulp/api/v3/repositories/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/"
              }
          },
          "present": {
              "ansible.role": {
                  "count": 16,
                  "href": "/pulp/api/v3/content/ansible/roles/?repository_version=/pulp/api/v3/repositories/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/"
              }
          },
          "removed": {}
      },
      "number": 1
  }


.. todo::

    Add a reference link to the live API


Reference (pulpcore): `Repository Version Creation API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_list>`_
