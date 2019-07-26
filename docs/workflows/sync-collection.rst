Synchronize Collections from Galaxy
===================================

Users can populate their Repositories with Collections from an external source, e.g.
https://galaxy.ansible.com by syncing their Repository.

Create a Repository
-------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

    {
        "_created": "2019-04-29T15:57:59.763712Z",
        "_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/",
        "_latest_version_href": null,
        "_versions_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/",
        "description": null,
        "name": "foo"
    }

Reference (pulpcore): `Repository API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#tag/repositories>`_


Create a CollectionRemote
-------------------------

Creating a CollectionRemote object allows Pulp to sync a whitelist of Collections from an external
content source. This is most commonly is ``https://galaxy.ansible.com/`` or another ``pulp_ansible``
instance.

In this example we will be syncing the ``testing.ansible_testing_content`` Collection from
``https://galaxy-dev.ansible.com``.

.. literalinclude:: ../_scripts/remote-collection.sh
   :language: bash

Remote GET Response::

    {
        "_created": "2019-04-29T13:51:10.860792Z",
        "_href": "/pulp/api/v3/remotes/ansible/collection/e1c65074-3a4f-4f06-837e-75a9a90f2c31/",
        "_last_updated": "2019-04-29T13:51:10.860805Z",
        "_type": "ansible.collection",
        "download_concurrency": 20,
        "name": "bar",
        "policy": "immediate",
        "proxy_url": null,
        "ssl_ca_certificate": null,
        "ssl_client_certificate": null,
        "ssl_client_key": null,
        "ssl_validation": true,
        "url": "https://galaxy-dev.ansible.com",
        "whitelist": "testing.ansible_testing_content"
    }

.. todo::

    Add a reference link to the live API


Sync Repository foo with CollectionRemote
-----------------------------------------

Use the CollectionRemote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch Collection content from the external source.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Repository Version GET Response (when complete)::


    {
        "_href": "/pulp/api/v3/repositories/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/",
        "_created": "2019-05-28T21:51:08.172095Z",
        "number": 1,
        "base_version": null,
        "content_summary": {
            "added": {
                "ansible.collection": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/ansible/collections/?repository_version_added=/pulp/api/v3/repositories/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/"
                }
            },
            "removed": {},
            "present": {
                "ansible.collection": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/ansible/collections/?repository_version=/pulp/api/v3/repositories/05813fa6-cf0b-435b-b54b-5a30fc370848/versions/1/"
                }
            }
        }
    }


.. todo::

    Add a reference link to the live API


Reference (pulpcore): `Repository Version Creation API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_list>`_
