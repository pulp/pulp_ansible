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
