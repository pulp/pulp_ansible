=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

0.2.0b2 (2019-08-12)
====================

Features
--------

- Fulltext Collection search is available with the ``q`` filter argument. A migration creates
  databases indexes to speed up the search.
  `#5075 <https://pulp.plan.io/issues/5075>`_
- Sync all collections (a full mirror) from Galaxy.
  `#5165 <https://pulp.plan.io/issues/5165>`_
- Mirror ansible collection
  `#5167 <https://pulp.plan.io/issues/5167>`_
- Added new fields to CollectionVersion and extended the CollectionVersion upload and sync to populate
  the data correctly. The serializer displays the new fields. The 'tags' field in serializer also has
  its own viewset for filtering on Tag objects system-wide.
  `#5198 <https://pulp.plan.io/issues/5198>`_
- Custom error handling and pagination for Galaxy API v3 is available.
  `#5224 <https://pulp.plan.io/issues/5224>`_
- Implements Galaxy API v3 collections and collection versions endpoints
  `#5225 <https://pulp.plan.io/issues/5225>`_


Bugfixes
--------

- Validating collection remote URL
  `#4996 <https://pulp.plan.io/issues/4996>`_
- Validates artifact creation when uploading a collection
  `#5209 <https://pulp.plan.io/issues/5209>`_
- Fixes exception when generating initial full text search index on more than one collection.
  `#5226 <https://pulp.plan.io/issues/5226>`_


Deprecations and Removals
-------------------------

- Removing whitelist field from CollectionRemote.
  `#5165 <https://pulp.plan.io/issues/5165>`_


Misc
----

- `#4970 <https://pulp.plan.io/issues/4970>`_, `#5106 <https://pulp.plan.io/issues/5106>`_, `#5223 <https://pulp.plan.io/issues/5223>`_


----


0.2.0b1 (2019-07-12)
====================

Features
--------

- Adds Artifact sha details to the Collection list and detail APIs.
  `#4827 <https://pulp.plan.io/issues/4827>`_
- Collection sync now provides basic progress reporting.
  `#5023 <https://pulp.plan.io/issues/5023>`_
- A new Collection uploader has been added to the pulp_ansible API at
  ``/pulp/api/v3/ansible/collections/``.
  `#5050 <https://pulp.plan.io/issues/5050>`_
- Collection filtering now supports the 'latest' boolean. When True, only the most recent version of
  each ``namespace`` and ``name`` combination is included in filter results.
  `#5076 <https://pulp.plan.io/issues/5076>`_


Bugfixes
--------

- Collection sync now creates a new RepositoryVersion even if no new Collection content was added.
  `#4920 <https://pulp.plan.io/issues/4920>`_
- Content present in a second sync now associates correctly with the newly created Repository Version.
  `#4997 <https://pulp.plan.io/issues/4997>`_
- Collection sync no longer logs errors about a missing directory named 'ansible_collections'
  `#4999 <https://pulp.plan.io/issues/4999>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#4875 <https://pulp.plan.io/issues/4875>`_
- Add documentation on Collection upload workflows.
  `#4939 <https://pulp.plan.io/issues/4939>`_
- Update the REST API docs to the latest by updating the committed openAPI schema.
  `#5001 <https://pulp.plan.io/issues/5001>`_
