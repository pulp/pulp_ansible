Pulp Ansible
============

This is the ``pulp_ansible`` repository which provides Pulp with the
ability to manage Ansible content e.g. Roles.

All REST API examples below use `httpie <https://httpie.org/doc>`__ to
perform the requests.

Install ``pulpcore``
--------------------

Follow the `installation
instructions <docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install plugin
--------------

Define installation steps here.

From source
~~~~~~~~~~~

1)  sudo -u pulp -i
2)  source ~/pulpvenv/bin/activate
3)  git clone https://github.com/pulp/pulp\_ansible.git
4)  cd pulp\_ansible
5)  python setup.py develop
6)  pulp-manager makemigrations pulp\_ansible
7)  pulp-manager migrate pulp\_ansible
8)  django-admin runserver
9)  sudo systemctl restart pulp\_resource\_manager
10) sudo systemctl restart pulp\_worker@1
11) sudo systemctl restart pulp\_worker@2

Install from PyPI
~~~~~~~~~~~~~~~~~

Define installation steps here.


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/api/v3/repositories/ name=foo``


.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/8d7cd67a-9421-461f-9106-2df8e4854f5f/",
        ...
    }

``$ export REPO_HREF=$(http :8000/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``


Create a new importer ``bar``
-----------------------------

``$ http POST :8000/api/v3/importers/ansible/ name=bar download_policy='immediate' sync_mode='additive' feed_url='https://galaxy.ansible.com/api/v1/roles/?namespace=ansible'``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/importers/ansible/13ac2d63-7b7b-401d-b71b-9a5af05aab3c/",
        ...
    }

``$ export IMPORTER_HREF=$(http :8000/api/v3/importers/ansible/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Sync repository ``foo`` using importer ``bar``
----------------------------------------------

``$ http POST $IMPORTER_HREF'sync/' repository=$REPO_HREF``


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

    [
        {
            "_href": "http://localhost:8000/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

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

