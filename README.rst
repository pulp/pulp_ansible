Pulp Ansible
============

Use ``pulp_ansible`` to create a private Galaxy. It doesn't have a UI currently, but using an API
you can:

* Mirror a subset of roles on-premise
* Mirror all of Galaxy’s roles on-premise
* Store private Ansible roles on-premise
* Install Roles from pulp_ansible using the `ansible-galaxy` CLI
* Version Role content over time and rollback if necessary

Issues are tracked `in Redmine <https://pulp.plan.io/projects/ansible_plugin/issues>`_. You can file
a new issue or feature request `here <https://pulp.plan.io/projects/ansible_plugin/issues/new>`_.
You can also ask questions in the #pulp-ansible channel on
`Freenode <https://webchat.freenode.net/>`_.


Install ``pulp-ansible`` using Ansible
--------------------------------------

pulp_ansible can be installed using an Ansible playbook and roles provided by pulpcore
`here <https://github.com/pulp/ansible-pulp3>`_. See
`this 2-min video <https://www.youtube.com/watch?v=-klj9NVTBTE>`_ showing that installer
installing pulp_ansible.

Install ``pulp-ansible`` From PyPI
----------------------------------

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-ansible

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions
<https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html#database-setup>`_

Install ``pulp-ansible`` from source
------------------------------------

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   git clone https://github.com/pulp/pulp_ansible.git
   cd pulp_ansible
   pip install -e .

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions
<https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html#database-setup>`_

Make and Run Migrations
-----------------------

.. code-block:: bash

   django-admin migrate ansible

Run Services
------------

.. code-block:: bash

   django-admin runserver
   gunicorn pulpcore.content:server --bind 'localhost:8080' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulp-resource-manager
   sudo systemctl restart pulp-worker@1

Quickstart
----------

All REST API examples bellow use `httpie <https://httpie.org/doc>`__ to perform the requests.
The ``httpie`` commands below assume that the user executing the commands has a ``.netrc`` file
in the home directory. The ``.netrc`` should have the following configuration:

.. code-block::

    machine localhost
    login admin
    password admin

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``httpie`` documentation on how to do that.

This documentation makes use of the `jq library <https://stedolan.github.io/jq/>`_
to parse the json received from requests, in order to get the unique urls generated
when objects are created. To follow this documentation as-is please install the jq
library with:

``$ sudo dnf install jq``


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/pulp/api/v3/repositories/ name=foo``


.. code:: json

    {
        "_href": "http://localhost:8000/pulp/api/v3/repositories/1/",
        ...
    }

``$ export REPO_HREF=$(http :8000/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``


Create a new remote ``bar``
-----------------------------

``$ http POST :8000/pulp/api/v3/remotes/ansible/ansible/ name=bar url='https://galaxy.ansible.com/api/v1/roles/?namespace__name=elastic'``

.. code:: json

    {
        "_href": "http://localhost:8000/pulp/api/v3/remotes/ansible/ansible/1/",
        ...
    }

``$ export REMOTE_HREF=$(http :8000/pulp/api/v3/remotes/ansible/ansible/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Sync repository ``foo`` using remote ``bar``
----------------------------------------------

``$ http POST ':8000'$REMOTE_HREF'sync/' repository=$REPO_HREF``


Look at the new Repository Version created
------------------------------------------

``$ http GET ':8000'$REPO_HREF'versions/1/'``

.. code:: json


  {
      "_added_href": "http://localhost:8000/pulp/api/v3/repositories/1/versions/1/added_content/",
      "_content_href": "http://localhost:8000/pulp/api/v3/repositories/1/versions/1/content/",
      "_href": "http://localhost:8000/pulp/api/v3/repositories/1/versions/1/",
      "_removed_href": "http://localhost:8000/pulp/api/v3/repositories/1/versions/1/removed_content/",
      "content_summary": {
          "ansible": 11
      },
      "created": "2018-03-12T19:23:31.000923Z",
      "number": 1
  }


Upload a Role to Pulp
---------------------

Download a role version.

``curl -L https://github.com/pulp/ansible-pulp3/archive/master.tar.gz -o pulp.tar.gz``

Create an Artifact by uploading the role version tarball to Pulp.

``$ export ARTIFACT_HREF=$(http --form POST http://localhost:8000/pulp/api/v3/artifacts/ file@pulp.tar.gz | jq -r '._href')``


Create a Role content unit
--------------------------

Create an Ansible role in Pulp.

``$ export ROLE_HREF=$(http http://localhost:8000/pulp/api/v3/content/ansible/roles/ namespace=pulp name=pulp | jq -r '._href')``


Create a ``role version`` from the Role and Artifact
-----------------------------------------------------

Create a content unit and point it to your Artifact and Role

``$ export CONTENT_HREF=$(http POST ':8000'${ROLE_HREF}versions/ version=0.0.1 _artifact=$ARTIFACT_HREF | jq -r '._href')``


Add content to repository ``foo``
---------------------------------

``$ http POST ':8000'$REPO_HREF'versions/' add_content_units:="[\"$CONTENT_HREF\"]"``


Create a Publication
-------------------------------------------------

``$ http POST :8000/pulp/api/v3/ansible/publications/ repository=$REPO_HREF``

.. code:: json

    {
        "task": "http://localhost:8000/pulp/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/"
    }

``$ export PUBLICATION_HREF=$(http :8000/pulp/api/v3/publications/ | jq -r '.results[0] | ._href')``


Create a Distribution for the Publication
-----------------------------------------

``$ http POST http://localhost:8000/pulp/api/v3/distributions/ name='baz' base_path='dev' publication=$PUBLICATION_HREF``


.. code:: json

    {
        "_href": "http://localhost:8000/pulp/api/v3/distributions/1/",
       ...
    }


Install the ansible kubernetes Role
-----------------------------------

Using a direct path
~~~~~~~~~~~~~~~~~~~

To install your role using a link to the direct tarball, do the following:

``$ ansible-galaxy install http://localhost:8080/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz,,elastic.elasticsearch``


Using the Pulp Galaxy API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, Pulp offers a built-in Galaxy API. To use this, set up your distribution in your
ansible config (e.g. ``~/.ansible.cfg`` or ``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server: http://localhost:8000/pulp_ansible/galaxy/dev

Then install your role using namespace and name:

.. code::

   $ ansible-galaxy install elastic.elasticsearch,6.2.4
   - downloading role 'elasticsearch', owned by elastic
   - downloading role from http://localhost:8080/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
   - extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
   - elastic.elasticsearch (6.2.4) was installed successfully

