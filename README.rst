Pulp Ansible
============

This is the ``pulp_ansible`` repository which provides Pulp with the
ability to manage Ansible content e.g. Roles.

All REST API examples below use `httpie <https://httpie.org/doc>`__ to
perform the requests.

Install ``pulpcore``
--------------------

Follow the `installation
instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
for pulpcore.

Install plugin
--------------

Install from PyPI
~~~~~~~~~~~~~~~~~

TODO: publish on PyPI

From source
~~~~~~~~~~~

0)  source ~/pulpvenv/bin/activate
1)  git clone https://github.com/pulp/pulp\_ansible.git
2)  cd pulp\_ansible
3)  python setup.py develop
4)  pulp-manager makemigrations pulp\_ansible
5)  pulp-manager migrate pulp\_ansible
6)  django-admin runserver
7)  sudo systemctl restart pulp\_resource\_manager
8) sudo systemctl restart pulp\_worker@1


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/api/v3/repositories/ name=foo``


.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/8d7cd67a-9421-461f-9106-2df8e4854f5f/",
        ...
    }

``$ export REPO_HREF=$(http :8000/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``


Create a new remote ``bar``
-----------------------------

``$ http POST :8000/api/v3/remotes/ansible/ name=bar download_policy='immediate' sync_mode='additive' url='https://galaxy.ansible.com/api/v1/roles/?namespace=ansible'``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/remotes/ansible/13ac2d63-7b7b-401d-b71b-9a5af05aab3c/",
        ...
    }

``$ export REMOTE_HREF=$(http :8000/api/v3/remotes/ansible/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Sync repository ``foo`` using remote ``bar``
----------------------------------------------

``$ http POST $REMOTE_HREF'sync/' repository=$REPO_HREF``


Look at the new Repository Version created
------------------------------------------

``$ http GET $REPO_HREF'versions/1/'``

.. code:: json


  {
      "_added_href": "http://localhost:8000/api/v3/repositories/933164fd-0514-4b0a-826f-c2e389ab1607/versions/1/added_content/",
      "_content_href": "http://localhost:8000/api/v3/repositories/933164fd-0514-4b0a-826f-c2e389ab1607/versions/1/content/",
      "_href": "http://localhost:8000/api/v3/repositories/933164fd-0514-4b0a-826f-c2e389ab1607/versions/1/",
      "_removed_href": "http://localhost:8000/api/v3/repositories/933164fd-0514-4b0a-826f-c2e389ab1607/versions/1/removed_content/",
      "content_summary": {
          "ansible": 11
      },
      "created": "2018-03-12T19:23:31.000923Z",
      "number": 1
  }


Upload ``pulp-0.0.1.tar`` to Pulp
-----------------------------

Create an Artifact by uploading the role version tar to Pulp.

``$ http --form POST http://localhost:8000/api/v3/artifacts/ file@pulp-0.0.1.tar``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/",
        ...
    }


Create a Role content unit
--------------------------

Create an Ansible role in Pulp.

``$ http http://localhost:8000/api/v3/content/ansible/roles/ namespace=pulp name=pulp``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/content/ansible/roles/3965b515-53a0-4667-a540-a76714a903d4/",
        "_versions_href": "http://localhost:8000/api/v3/content/ansible/roles/3965b515-53a0-4667-a540-a76714a903d4/versions/",
        "name": "pulp",
        "namespace": "pulp"
    }


Create a ``role version`` from the Role and Artifact
-----------------------------------------------------

Create a content unit and point it to your Artifact and Role

``$ http POST http://localhost:8000/api/v3/content/ansible/roles/3965b515-53a0-4667-a540-a76714a903d4/versions/ version=0.0.1 artifact="http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/"``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/content/ansible/roles/3965b515-53a0-4667-a540-a76714a903d4/versions/183d532c-37e8-4c0a-a00e-5a80b2de4162/",
        "artifact": "http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/",
        "version": "0.0.1",
        "type": "ansible-role-version"
    }

``$ export CONTENT_HREF=$(http :8000/api/v3/content/ansible/roles/3965b515-53a0-4667-a540-a76714a903d4/versions/ | jq -r '.results[] | select(.version == "0.0.1") | ._href')``


Add content to repository ``foo``
---------------------------------

``$ http POST $REPO_HREF'versions/' add_content_units:="[\"$CONTENT_HREF\"]"``


Create an Ansible publisher
---------------------------

``$ http POST http://localhost:8000/api/v3/publishers/ansible/ name=bar``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/publishers/ansible/bar/",
        ...
    }


``$ export PUBLISHER_HREF=$(http :8000/api/v3/publishers/ansible/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Use the ``bar`` Publisher to create a Publication
-------------------------------------------------

``$ http POST $PUBLISHER_HREF'publish/' repository=$REPO_HREF``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
        "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
    }

``$ export PUBLICATION_HREF=$(http :8000/api/v3/publications/ | jq -r --arg PUBLISHER_HREF "$PUBLISHER_HREF" '.results[] | select(.publisher==$PUBLISHER_HREF) | ._href')``


Create a Distribution for the Publication
---------------------------------------

``$ http POST http://localhost:8000/api/v3/distributions/ name='baz' base_path='dev' publication=$PUBLICATION_HREF``


.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/distributions/9b29f1b2-6726-40a2-988a-273d3f009a41/",
       ...
    }


Install the ansible kubernetes Role
-----------------------------------

``$ ansible-galaxy install http://localhost:8000/content/dev/ansible/kubernetes-modules/v0.3.1-6.tar,,ansible.kubernetes``

