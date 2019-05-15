Pulp Ansible
============

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


Install using Ansible
---------------------

pulpcore provides an `Ansible Installer <https://github.com/pulp/ansible-pulp>`_ that can be used to
install ``pulp_ansible``. For example if your host is in your Ansible inventory as ``myhost`` you
can install onto it with:

.. code-block:: bash

    git clone https://github.com/pulp/ansible-pulp.git

Create your pulp_ansible.yml playbook to use with the installer:

.. code-block:: yaml

   ---
   - hosts: all
     vars:
       pulp_secret_key: secret
       pulp_default_admin_password: password
       pulp_install_plugins:
         pulp-ansible:
           app_label: "ansible"
     roles:
       - pulp-database
       - pulp-workers
       - pulp-resource-manager
       - pulp-webserver
       - pulp-content
     environment:
       DJANGO_SETTINGS_MODULE: pulpcore.app.settings

Then install it onto ``myhost`` with:

.. code-block:: bash

    ansible-playbook pulp_ansible.yaml -l myhost


Install with pulplift
---------------------

`pulplift <https://github.com/pulp/pulplift>`_ combines the Ansible installer above with `Vagrant
<https://www.vagrantup.com/intro/index.html>`_ to easily try ``pulp_ansible`` on a local VM.

First you'll need to `install Vagrant <https://www.vagrantup.com/docs/installation/>`_.

.. code-block:: bash

    git clone --recurse-submodules https://github.com/pulp/pulplift.git
    cd pulplift

Configure pulplift to install ``pulp_ansible``:

.. code-block:: bash

    cat >local.user-config.ymll <<EOL
    pulp_default_admin_password: password
    pulp_install_plugins:
      pulp-ansible:
        app_label: "ansible"
    pulp_secret_key: "unsafe_default"
    EOL

Then run Vagrant up for fedora30 using:

.. code-block:: bash

    vagrant up pulp3-sandbox-fedora30

Then once finished ssh to your ``pulp_ansible`` environment with:

.. code-block:: bash

    vagrant ssh pulp3-sandbox-fedora30


Install ``pulp_ansible`` From PyPI
----------------------------------

.. code-block:: bash

   pip install pulp-ansible

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/
instructions.html#database-setup>`_


Install ``pulp_ansible`` from source
------------------------------------

.. code-block:: bash

   git clone https://github.com/pulp/pulp_ansible.git
   cd pulp_ansible
   pip install -e .

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/
instructions.html#database-setup>`_


Run Migrations
--------------

.. code-block:: bash

   django-admin migrate ansible


Run Services
------------

.. code-block:: bash

   django-admin runserver 24817
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulp-resource-manager
   sudo systemctl restart pulp-worker@1


Configuring an API Client
-------------------------

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

``$ http POST :24817/pulp/api/v3/repositories/ name=foo``


.. code:: json

    {
        "_href": "/pulp/api/v3/repositories/51742e85-96f8-4bc6-a232-b408f4631d98/",
        ...
    }

``$ export REPO_HREF=$(http :24817/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``


Create a new remote ``bar``
-----------------------------

``$ http POST :24817/pulp/api/v3/remotes/ansible/ansible/ name=bar url='https://galaxy.ansible.com/api/v1/roles/?namespace__name=elastic'``

.. code:: json

    {
        "_href": "/pulp/api/v3/remotes/ansible/ansible/e1c65074-3a4f-4f06-837e-75a9a90f2c31/",
        ...
    }

``$ export REMOTE_HREF=$(http :24817/pulp/api/v3/remotes/ansible/ansible/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Sync repository ``foo`` using remote ``bar``
----------------------------------------------

``$ http POST ':24817'$REMOTE_HREF'sync/' repository=$REPO_HREF``


Look at the new Repository Version created
------------------------------------------

``$ http GET ':24817'$REPO_HREF'versions/1/'``

.. code:: json


  {
      "_href": "/pulp/api/v3/repositories/78286e2c-829a-4a8c-a3ca-3a2e490e01a7/versions/1/",
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


Upload a Role to Pulp
---------------------

Download a role version.

``curl -L https://github.com/geerlingguy/ansible-role-postgresql/archive/master.tar.gz -o pg.tar.gz``

Create an Artifact by uploading the role version tarball to Pulp.

``$ export ARTIFACT_HREF=$(http --form POST :24817/pulp/api/v3/artifacts/ file@pg.tar.gz | jq -r '._href')``


Create a Role content unit
--------------------------

Create a Role in Pulp.

``$ export ROLE_HREF=$(http :24817/pulp/api/v3/content/ansible/roles/ namespace=pulp name=postgresql version=0.0.1 _artifact=$ARTIFACT_HREF | jq -r '._href')``


Add content to repository ``foo``
---------------------------------

``$ http POST ':24817'$REPO_HREF'versions/' add_content_units:="[\"$ROLE_HREF\"]"``

.. code:: json

    {
        "task": "/pulp/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/"
    }


Create a Distribution for Repository 'foo'
------------------------------------------

This will distribute the 'latest' RepositoryVersion always.

``$ http POST :24817/pulp/api/v3/distributions/ansible/ansible/ name='baz' base_path='dev' repository=$REPO_HREF``


.. code:: json

    {
        "_href": "/pulp/api/v3/tasks/2610a47e-4e88-4e8c-9d2e-c71734ae7b39/",
       ...
    }



Create a Distribution for a RepositoryVersion
---------------------------------------------

Say you always want to distribute version 1 of Repository 'foo' even if more versions are created.

``$ http POST :24817/pulp/api/v3/distributions/ansible/ansible/ name='baz' base_path='dev' repository_version=${REPO_HREF}versions/1/``


.. code:: json

    {
        "_href": "/pulp/api/v3/tasks/2610a47e-4e88-4e8c-9d2e-c71734ae7b39/",
       ...
    }



Install the ansible kubernetes Role
-----------------------------------

Using a direct path
~~~~~~~~~~~~~~~~~~~

To install your role using a link to the direct tarball, do the following:

``$ ansible-galaxy install http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz,,elastic.elasticsearch``


Using the Pulp Galaxy API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, Pulp offers a built-in Galaxy API. To use this, set up your distribution in your
ansible config (e.g. ``~/.ansible.cfg`` or ``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server: http://localhost:24817/pulp_ansible/galaxy/dev

Then install your role using namespace and name:

.. code::

   $ ansible-galaxy install elastic.elasticsearch,6.2.4
   - downloading role 'elasticsearch', owned by elastic
   - downloading role from http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
   - extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
   - elastic.elasticsearch (6.2.4) was installed successfully


Collection Support
------------------

.. warning::

    The 'Collection' content type is currently in tech-preview. Breaking changes could be introduced
    in the future.

pulp_ansible can manage the `multi-role repository content <https://galaxy.ansible.com/docs/using/
installing.html#multi-role-repositories>`_ referred to as a `Collection`. The following features are
supported:

* `mazer upload` - Upload a Collection to pulp_ansible for association with one or more
  repositories.
* `mazer install` - Install a Collection from pulp_ansible.


Configuring Collection Support
------------------------------

You'll have to specify the protocol and hostname the pulp_ansible REST API is being served on. For
pulp_ansible to interact with `mazer` correctly it needs the entire hostname. This is done using the
`ANSIBLE_HOSTNAME` setting in Pulp. For example if its serving with http on localhost it would be::

    export PULP_ANSIBLE_API_HOSTNAME='http://localhost:24817'
    export PULP_ANSIBLE_CONTENT_HOSTNAME='http://localhost:24816/pulp/content'

or in your systemd environment:

    Environment="PULP_ANSIBLE_API_HOSTNAME=http://localhost:24817"
    Environment="PULP_ANSIBLE_CONTENT_HOSTNAME=http://localhost:24816/pulp/content"


Mazer Configuration
-------------------

`Install mazer <https://galaxy.ansible.com/docs/mazer/install.html#latest-stable-release>`_ and
use the `url` option to point to the `Distribution` your content should fetch from. For example,
using the `Distribution` created in the sync workflow, the config would be::

    server:
      url: http://localhost:24817/pulp_ansible/galaxy/dev

This is assuming you have the `Collection` content exposed at a Distribution created with
`base_path=dev` (as in the example above).


Mazer publish
-------------

You can use `mazer` to publish any `built artifact <https://github.com/ansible/mazer/#building-
ansible-content-collection-artifacts-with-mazer-build>`_ to pulp_ansible by running::

    mazer publish path/to/artifact.tar.gz

For example if you have mazer installed and configured the script below will upload a Collection to
pulp_ansible and display it::

    $ git clone https://github.com/ansible/mazer.git
    $ cd mazer/tests/ansible_galaxy/collection_examples/hello/
    $ mazer build
    $ mazer publish releases/greetings_namespace-hello-11.11.11.tar.gz
    $ http :24817/pulp/api/v3/content/ansible/collections/
    HTTP/1.1 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Connection: close
    Content-Length: 357
    Content-Type: application/json
    Date: Tue, 30 Apr 2019 22:12:06 GMT
    Server: gunicorn/19.9.0
    Vary: Accept, Cookie
    X-Frame-Options: SAMEORIGIN

    {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "_artifact": "/pulp/api/v3/artifacts/8d77cbc1-fcc7-4239-b369-323ef2080e2f/",
                "_created": "2019-04-30T22:12:01.452493Z",
                "_href": "/pulp/api/v3/content/ansible/collections/505e7a21-49c6-4287-936e-b043ec6f76d1/",
                "_type": "ansible.collection",
                "name": "hello",
                "namespace": "greetings_namespace",
                "version": "11.11.11"
            }
        ]
    }

Note that this does not add the Collection to any Repository Version. You can associate the `hello`
unit with a two step process:

1. Create a new RepositoryVersion that includes the Collection
2. Create a new Publication that references the new RepositoryVersion from step 1.
3. Update the Distribution serving `mazer` to serve the new Publication from step 2.

You could do these steps with a script like::

    # Create a Repository
    http POST :24817/pulp/api/v3/repositories/ name=foo
    export REPO_HREF=$(http :24817/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')

    # Find the 'hello' collection
    export COLLECTION_HREF=$(http :24817/pulp/api/v3/content/ansible/collections/ | jq -r '.results[0]._href')

    # Create a Repository Version with the 'hello' collection
    http POST ':24817'$REPO_HREF'versions/' add_content_units:="[\"$COLLECTION_HREF\"]"

    # Create a Distribution
    http POST :24817/pulp/api/v3/distributions/ansible/ansible/ name='baz' base_path='dev' repository=$REPO_HREF


Mazer install
-------------

You can use `mazer` to install a collection by its namespace and name from pulp_ansible using the
`install` command. For example to install the `hello` collection from above you can specify::

    mazer install greetings_namespace.hello


This assumes that the `hello` Collection is being served by the Distribution `mazer` is configured
to use.
