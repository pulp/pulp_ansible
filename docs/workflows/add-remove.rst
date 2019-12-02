.. _add-remove:

Add/Remove Content to a Repository
==================================

Whether your Role was fetched with a sync or uploaded, any content can also be added/removed to a
repository manually::

    $ http POST $BASE_ADDR$REPO_HREF'modify/' \
                    add_content_units:="[\"$CONTENT_HREF\"]"


This is entirely implemented by `pulpcore`, please see their reference docs for more information.

Reference (pulpcore): `Repository Version Creation API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_create>`_
