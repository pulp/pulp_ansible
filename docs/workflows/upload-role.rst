Upload Content
==============

Upload an Artifact to Pulp
--------------------------

This example will upload the ``geerlingguy/ansible-role-postgresql`` role. You can download that
locally with::

    curl -L https://github.com/geerlingguy/ansible-role-postgresql/archive/master.tar.gz -o pg.tar.gz


Each Artifact in Pulp represents a file. They can be created during sync or created manually by
uploading a file::

    $ export ARTIFACT_HREF=$(http --form POST :24817/pulp/api/v3/artifacts/ file@pg.tar.gz | jq -r '._href')


Response::

    {
        "_href": "/pulp/api/v3/artifacts/5741288b-7ed5-4199-a5a6-3d82fb97055c/",
    }


Reference (pulpcore): `Artifact API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#tag/artifacts>`_


Create a Role from the Artifact
-------------------------------

Now that Pulp has the tarball, its time to make it into a Role unit of content. We hope to add
auto-parsing of tarball data, but currently all metadata is client supplied at creation time::

    $ http :24817/pulp/api/v3/content/ansible/roles/ namespace=pulp name=postgresql version=0.0.1 _artifact=$ARTIFACT_HREF


Response::

    {
        "_href": "/pulp/api/v3/content/ansible/roles/b059a742-1d5d-452d-8085-856844b70f1a/",
    }


Create a variable for convenience::

    $ export CONTENT_HREF=$(http $BASE_ADDR/pulp/api/v3/content/ansible/roles/ | jq -r '.results[] | select(.filename == "pg.tar.gz") | ._href')


.. todo::

    Link to live API docs for Role creation


Add Content to a Repository
---------------------------

See :ref:`add-remove`
