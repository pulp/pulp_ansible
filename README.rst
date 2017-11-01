Template to create your own plugin
==================================

This is the ``plugin_template`` repository to help plugin writers
get started and write their own plugin for `Pulp Project
3.0+ <https://pypi.python.org/pypi/pulpcore/>`__.

Clone this repository and run the provided ``rename.py`` script to create
a skeleton for your plugin with the name of your choice. It will contain
``setup.py``, expected plugin layout and stubs for necessary classes and methods.

``$ git clone https://github.com/pulp/plugin_template.git``

``$ cd plugin_template``

``$ ./rename.py your_plugin_name``

Check `Plugin Writer's Guide <http://docs.pulpproject.org/en/3.0/nightly/plugins/plugin-writer/index.html>`__
for more details and suggestions on plugin implementaion.

Below are some ideas for how to document your plugin.


All REST API examples below use `httpie <https://httpie.org/doc>`__ to
perform the requests.

Install ``pulpcore``
--------------------

Follow the `installation
instructions <docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install plugin
--------------

From source
~~~~~~~~~~~

Define installation steps here.

Install from PyPI
~~~~~~~~~~~~~~~~~

Define installation steps here.


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/api/v3/repositories/ name=foo``

Add an Importer to repository ``foo``
-------------------------------------

Add important details about your Importer and provide examples.

``$ http POST http://localhost:8000/api/v3/repositories/foo/importers/plugin-template/ some=params``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/importers/plugin-template/bar/",
        ...
    }

Add a Publisher to repository ``foo``
-------------------------------------

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/plugin-template/ name=bar``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/publishers/plugin-template/bar/",
        ...
    }

Add a Distribution to Publisher ``bar``
---------------------------------------

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/plugin-template/bar/distributions/ some=params``

Sync repository ``foo`` using Importer ``bar``
----------------------------------------------

Use ``plugin-template`` Importer:

``http POST http://localhost:8000/api/v3/repositories/foo/importers/plugin-template/bar/sync/``

Add content to repository ``foo``
---------------------------------

``$ http POST http://localhost:8000/api/v3/repositorycontents/ repository='http://localhost:8000/api/v3/repositories/foo/' content='http://localhost:8000/api/v3/content/plugin-template/a9578a5f-c59f-4920-9497-8d1699c112ff/'``

Create a Publication using Publisher ``bar``
--------------------------------------------

Dispatch the Publish task

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/plugin-template/bar/publish/``

.. code:: json

    [
        {
            "_href": "http://localhost:8000/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

Check status of a task
----------------------

``$ http GET http://localhost:8000/api/v3/tasks/82e64412-47f8-4dd4-aa55-9de89a6c549b/``

Download ``foo.tar.gz`` from Pulp
---------------------------------

``$ http GET http://localhost:8000/content/foo/foo.tar.gz``
