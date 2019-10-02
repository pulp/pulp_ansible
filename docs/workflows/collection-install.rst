.. _collection-cli:

Install a Collection, hosted by Pulp, using ``ansible-galaxy``
==============================================================

Configuration
-------------

`Install ansible <https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html>`_ and
edit the file::

    ~/.ansible.cfg

using the `server` option to point to the `Distribution` your content should fetch from. For example,
using the `Distribution` created in the sync workflow, the config would be::

.. code::

    [galaxy]
    server: http://localhost/pulp_ansible/galaxy/dev

This is assuming you have the `Collection` content exposed at a Distribution created with
`base_path=dev` (as in the example above).


.. _collection-publish:

Publish
-------

You can use `ansible-galaxy` to publish any `built artifact <https://github.com/ansible/mazer/#building-
ansible-content-collection-artifacts-with-mazer-build>`_ to pulp_ansible by running::

    ansible-galaxy collection publish path/to/artifact.tar.gz

For example if you have ansible-galaxy installed and configured the script below will upload a
Collection to pulp_ansible and display it::

    $ git clone https://github.com/ansible/mazer.git
    $ cd mazer/tests/ansible_galaxy/collection_examples/hello/
    $ ansible-galaxy build
    $ ansible-galaxy publish releases/greetings_namespace-hello-11.11.11.tar.gz
    $ http :80/pulp/api/v3/content/ansible/collections/
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
                "pulp_created": "2019-04-30T22:12:01.452493Z",
                "pulp_href": "/pulp/api/v3/content/ansible/collections/505e7a21-49c6-4287-936e-b043ec6f76d1/",
                "_type": "ansible.collection",
                "name": "hello",
                "namespace": "greetings_namespace",
                "sha1": "e33a25765f87bfdb6c5cba9c7a5b4acb78933fd3",
                "sha224": "8e2748f03e0180930d22889c2207811776064b7a5a7049697c9e7d99",
                "sha256": "7ca7812c631be57e27b182f58cffc4d891c392d7358add848894a8b1ef87a82a",
                "sha384": "00fdd9bb38212072130d09b0602e47b0542dd39e364456cf7890c67245183638fe0f1fb8735a26749b5798228e4575ff",
                "sha512": "edd1224d8b8276d36b2743b7ca41e51ac1eb217d095143240b6b4bd448804d70c916bb826b9d57c130cdc2c299c8b46a55cfdffef11f2483016bc85a07a8ef0c",
                "version": "11.11.11"
            }
        ]
    }

Note that this does not add the Collection to any Repository Version. You can associate the `hello`
unit with a two step process:

1. Create a new RepositoryVersion that includes the Collection
2. Update the Distribution serving `ansible-galaxy` to serve the new RepositoryVersion from step 1.

You could do these steps with a script like::

    # Create a Repository
    http POST :/pulp/api/v3/repositories/ name=foo
    export REPO_HREF=$(http :/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | .pulp_href')

    # Find the 'hello' collection
    export COLLECTION_HREF=$(http :/pulp/api/v3/content/ansible/collections/ | jq -r '.results[0].pulp_href')

    # Create a Repository Version with the 'hello' collection
    http POST ':'$REPO_HREF'versions/' add_content_units:="[\"$COLLECTION_HREF\"]"

    # Create a Distribution
    http POST :/pulp/api/v3/distributions/ansible/ansible/ name='baz' base_path='dev' repository=$REPO_HREF


Install
-------

You can use `ansible-galaxy` to install a collection by its namespace and name from pulp_ansible
using the `install` command. For example to install the `hello` collection from above into a
directory `~/collections` you can specify::

    ansible-galaxy install greetings_namespace.hello -p ~/collections


This assumes that the `hello` Collection is being served by the Distribution `ansible-galaxy` is
configured
to use.
