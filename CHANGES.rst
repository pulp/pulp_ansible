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

0.4.2 (2020-10-09)
==================

Bugfixes
--------

- Update Collection serializer to match Galaxy v2
  `#7647 <https://pulp.plan.io/issues/7647>`_
- Fix galaxy collection endpoint results for empty repos
  `#7669 <https://pulp.plan.io/issues/7669>`_


----


0.4.1 (2020-09-30)
==================

Bugfixes
--------

- Fixing docs-blob file parser
  `#7551 <https://pulp.plan.io/issues/7551>`_
- Sync CollectionVersion metadata
  `#7632 <https://pulp.plan.io/issues/7632>`_


----


0.4.0 (2020-09-23)
==================

Bugfixes
--------

- List highest versions per repository
  `#7428 <https://pulp.plan.io/issues/7428>`_
- Fix skipped collections at requirements.yml
  `#7512 <https://pulp.plan.io/issues/7512>`_


----


0.3.0 (2020-09-09)
==================

Features
--------

- Add endpoint to show docs_blob for a CollectionVersion
  `#7397 <https://pulp.plan.io/issues/7397>`_
- Allow the requirements file field on remotes to be of longer length.
  `#7434 <https://pulp.plan.io/issues/7434>`_
- Sync docs_blob information for collection versions
  `#7439 <https://pulp.plan.io/issues/7439>`_


Bugfixes
--------

- Replace URLField with CharField
  `#7353 <https://pulp.plan.io/issues/7353>`_
- Pagination query params according to API versions.
  v1 and v2 - `page` and `page_size`
  v3 or above - `offset` and `limit`
  `#7396 <https://pulp.plan.io/issues/7396>`_
- Build collections URL according to requirements.yml
  `#7412 <https://pulp.plan.io/issues/7412>`_


Deprecations and Removals
-------------------------

- Changed V3 pagination to match Galaxy V3 API pagination
  `#7435 <https://pulp.plan.io/issues/7435>`_


Misc
----

- `#7453 <https://pulp.plan.io/issues/7453>`_


----


0.2.0 (2020-08-17)
==================

Features
--------

- Allow a Remote to be associated with a Repository and automatically use it when syncing the
  Repository.
  `#7194 <https://pulp.plan.io/issues/7194>`_


Deprecations and Removals
-------------------------

- Moved the role remote path from ``/pulp/api/v3/remotes/ansible/ansible/`` to
  ``/pulp/api/v3/remotes/ansible/role/`` to be consistent with
  ``/pulp/api/v3/remotes/ansible/collection/``.
  `#7305 <https://pulp.plan.io/issues/7305>`_


Misc
----

- `#6718 <https://pulp.plan.io/issues/6718>`_


----


0.2.0b15 (2020-07-14)
=====================

Features
--------

- Enable token authentication for syncing Collections.
  Added `auth_url` and `token` `fields <https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#configuring-the-ansible-galaxy-client>`_ to `CollectionRemote`
  `#6540 <https://pulp.plan.io/issues/6540>`_


----


0.2.0b14 (2020-06-19)
=====================

Bugfixes
--------

- Make default page size equals to 100
  `#5494 <https://pulp.plan.io/issues/5494>`_
- Including requirements.txt on MANIFEST.in
  `#6889 <https://pulp.plan.io/issues/6889>`_


Misc
----

- `#6772 <https://pulp.plan.io/issues/6772>`_


----


0.2.0b13 (2020-05-28)
=====================

Features
--------

- Increased max length for `documentation`, `homepage`, `issues`, `repository` in `CollectionVersion`
  `#6648 <https://pulp.plan.io/issues/6648>`_


Bugfixes
--------

- Galaxy V3 download_url now uses fully qualified URL
  `#6510 <https://pulp.plan.io/issues/6510>`_
- Include readable error messages on user facing logger
  `#6657 <https://pulp.plan.io/issues/6657>`_
- Fix filename generation for ansible collection artifacts.
  `#6855 <https://pulp.plan.io/issues/6855>`_


Improved Documentation
----------------------

- Updated the required roles names
  `#6760 <https://pulp.plan.io/issues/6760>`_


Misc
----

- `#6673 <https://pulp.plan.io/issues/6673>`_, `#6848 <https://pulp.plan.io/issues/6848>`_, `#6850 <https://pulp.plan.io/issues/6850>`_


----


0.2.0b12 (2020-04-30)
=====================

Improved Documentation
----------------------

- Documented bindings installation on dev environment
  `#6390 <https://pulp.plan.io/issues/6390>`_


Misc
----

- `#6391 <https://pulp.plan.io/issues/6391>`_


----


0.2.0b11 (2020-03-13)
=====================

Features
--------

- Add support for syncing collections from Automation Hub's v3 api.
  `#6132 <https://pulp.plan.io/issues/6132>`_


Bugfixes
--------

- Including file type extension when uploading collections.
  This comes with a data migration that will fix incorrect fields for already uploaded collections.
  `#6223 <https://pulp.plan.io/issues/6223>`_


Improved Documentation
----------------------

- Added docs on how to use the new scale testing tools.
  `#6272 <https://pulp.plan.io/issues/6272>`_


Misc
----

- `#6155 <https://pulp.plan.io/issues/6155>`_, `#6223 <https://pulp.plan.io/issues/6223>`_, `#6272 <https://pulp.plan.io/issues/6272>`_, `#6300 <https://pulp.plan.io/issues/6300>`_


----


0.2.0b10 (2020-02-29)
=====================

Bugfixes
--------

- Includes webserver snippets in the packaged version also.
  `#6248 <https://pulp.plan.io/issues/6248>`_


Misc
----

- `#6250 <https://pulp.plan.io/issues/6250>`_


----


0.2.0b9 (2020-02-28)
====================

Bugfixes
--------

- Fix 404 error with ansible-galaxy 2.10.0 while staying compatible with 2.9.z CLI clients also.
  `#6239 <https://pulp.plan.io/issues/6239>`_


Misc
----

- `#6188 <https://pulp.plan.io/issues/6188>`_


----


0.2.0b8 (2020-02-02)
====================

Bugfixes
--------

- Fixed ``ansible-galaxy publish`` command which was failing with a 400 error.
  `#5905 <https://pulp.plan.io/issues/5905>`_
- Fixes ``ansible-galaxy role install`` when installing from Pulp.
  `#5929 <https://pulp.plan.io/issues/5929>`_


Improved Documentation
----------------------

- Heavy overhaul of workflow docs to be two long pages that are focused on the ``ansible-galaxy`` cli.
  `#4889 <https://pulp.plan.io/issues/4889>`_


Misc
----

- `#5867 <https://pulp.plan.io/issues/5867>`_, `#5929 <https://pulp.plan.io/issues/5929>`_, `#5930 <https://pulp.plan.io/issues/5930>`_, `#5931 <https://pulp.plan.io/issues/5931>`_


----


0.2.0b7 (2019-12-16)
====================

Features
--------

- Add "modify" endpoint as ``/pulp/api/v3/repositories/ansible/ansible/<uuid>/modify/``.
  `#5783 <https://pulp.plan.io/issues/5783>`_


Improved Documentation
----------------------

- Adds copyright notice to source.
  `#4592 <https://pulp.plan.io/issues/4592>`_


Misc
----

- `#5693 <https://pulp.plan.io/issues/5693>`_, `#5701 <https://pulp.plan.io/issues/5701>`_, `#5757 <https://pulp.plan.io/issues/5757>`_


----


0.2.0b6 (2019-11-20)
====================

Features
--------

- Add Ansible Collection endpoint.
  `#5520 <https://pulp.plan.io/issues/5520>`_
- Added `since` filter for CollectionImport messsages.
  `#5522 <https://pulp.plan.io/issues/5522>`_
- Add a tags filter by which to filter collection versions.
  `#5571 <https://pulp.plan.io/issues/5571>`_
- Allow users to update `deprecated` for collections endpoint.
  `#5577 <https://pulp.plan.io/issues/5577>`_
- Add the ability to set a certification status for a collection version.
  `#5579 <https://pulp.plan.io/issues/5579>`_
- Add sorting parameters to the collection versions endpoint.
  `#5621 <https://pulp.plan.io/issues/5621>`_
- Expose the deprecated field on collection versions and added a deprecated filter.
  `#5645 <https://pulp.plan.io/issues/5645>`_
- Added filters to v3 collection version endpoint
  `#5670 <https://pulp.plan.io/issues/5670>`_


Bugfixes
--------

- Reverting back to the older upload serializers.
  `#5555 <https://pulp.plan.io/issues/5555>`_
- Fix bug where CollectionImport was not being created in viewset causing 404s for galaxy.
  `#5569 <https://pulp.plan.io/issues/5569>`_
- Fixed an old call to _id in a collection task.
  `#5572 <https://pulp.plan.io/issues/5572>`_
- Fix 500 error for /pulp/api/v3/ page and drf_yasg error on api docs.
  `#5748 <https://pulp.plan.io/issues/5748>`_


Deprecations and Removals
-------------------------

- Change `_id`, `_created`, `_last_updated`, `_href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`_
- Remove "_" from `_versions_href`, `_latest_version_href`
  `#5548 <https://pulp.plan.io/issues/5548>`_
- Removing base field: `_type` .
  `#5550 <https://pulp.plan.io/issues/5550>`_
- Change `is_certified` to `certification` enum on `CollectionVersion`.
  `#5579 <https://pulp.plan.io/issues/5579>`_
- Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

  Creating / listing / editing / deleting Ansible repositories is now performed on /pulp/api/v3/ansible/ansible/ instead of /pulp/api/v3/repositories/. Only Ansible content can be present in a Ansible repository, and only a Ansible repository can hold Ansible content.
  `#5625 <https://pulp.plan.io/issues/5625>`_
- Removing unnecessary `DELETE` action for `set_certified` method.
  `#5711 <https://pulp.plan.io/issues/5711>`_


Misc
----

- `#4554 <https://pulp.plan.io/issues/4554>`_, `#5580 <https://pulp.plan.io/issues/5580>`_, `#5629 <https://pulp.plan.io/issues/5629>`_


----


0.2.0b5 (2019-10-01)
====================

Misc
----

- `#5462 <https://pulp.plan.io/issues/5462>`_, `#5468 <https://pulp.plan.io/issues/5468>`_


----


0.2.0b3 (2019-09-18)
====================

Features
--------

- Setting `code` on `ProgressBar`.
  `#5184 <https://pulp.plan.io/issues/5184>`_
- Add galaxy-importer into import_collection to parse and validate collection.
  `#5239 <https://pulp.plan.io/issues/5239>`_
- Add Collection upload endpoint to Galaxy V3 API.
  `#5243 <https://pulp.plan.io/issues/5243>`_
- Introduces the `GALAXY_API_ROOT` setting that lets you re-root the Galaxy API.
  `#5244 <https://pulp.plan.io/issues/5244>`_
- Add `requirements.yaml <https://docs.ansible.com/ansible/devel/dev_guide/collections_tech_preview.html#install-multiple-collections-with-a-requirements-file>`_ specification support to collection sync.
  `#5250 <https://pulp.plan.io/issues/5250>`_
- Adding `is_highest` filter for Collection Version.
  `#5278 <https://pulp.plan.io/issues/5278>`_
- Add certified collections status support.
  `#5287 <https://pulp.plan.io/issues/5287>`_
- Support pulp-to-pulp syncing of collections by expanding galaxy API views/serializers
  `#5288 <https://pulp.plan.io/issues/5288>`_
- Add model for tracking collection import status.
  `#5300 <https://pulp.plan.io/issues/5300>`_
- Add collection imports endpoints.
  `#5301 <https://pulp.plan.io/issues/5301>`_
- Uploaded collections through the Galaxy V2 and V3 APIs now auto-create a RepositoryVersion for the
  Repository associated with the AnsibleDistribution.
  `#5334 <https://pulp.plan.io/issues/5334>`_
- Added support for `ansible-galaxy collections` command and removed mazer.
  `#5335 <https://pulp.plan.io/issues/5335>`_
- CollectionImport object is created on collection upload.
  `#5358 <https://pulp.plan.io/issues/5358>`_
- Adds id field to collection version items returned by API.
  `#5365 <https://pulp.plan.io/issues/5365>`_
- The Galaxy V3 artifacts/collections/ API now logs correctly during the import process.
  `#5366 <https://pulp.plan.io/issues/5366>`_
- Write galaxy-importer result of contents and docs_blob into CollectionVersion model
  `#5368 <https://pulp.plan.io/issues/5368>`_
- The Galaxy v3 API validates the tarball's binary data before import using the optional arguments
  `expected_namespace`, `expected_name`, and `expected_version`.
  `#5422 <https://pulp.plan.io/issues/5422>`_
- Settings ``ANSIBLE_API_HOSTNAME`` and ``ANSIBLE_CONTENT_HOSTNAME`` now have defaults that use your
  FQDN, which works with `the installer <https://github.com/pulp/ansible-pulp>`_ defaults.
  `#5466 <https://pulp.plan.io/issues/5466>`_


Bugfixes
--------

- Treating how JSONFields will be handled by OpenAPI.
  `#5299 <https://pulp.plan.io/issues/5299>`_
- Galaxy API v3 collection upload returns valid imports URL.
  `#5357 <https://pulp.plan.io/issues/5357>`_
- Fix CollectionVersion view imcompatibilty with ansible-galaxy.
  Fixes ansible issue https://github.com/ansible/ansible/issues/62076
  `#5459 <https://pulp.plan.io/issues/5459>`_


Improved Documentation
----------------------

- Added documentation on all settings.
  `#5244 <https://pulp.plan.io/issues/5244>`_


Deprecations and Removals
-------------------------

- Removing `latest` filter Collection Version.
  `#5227 <https://pulp.plan.io/issues/5227>`_
- Removed support for mazer cli.
  `#5335 <https://pulp.plan.io/issues/5335>`_
- Renamed _artifact on content creation to artifact.
  `#5428 <https://pulp.plan.io/issues/5428>`_


Misc
----

- `#4681 <https://pulp.plan.io/issues/4681>`_, `#5236 <https://pulp.plan.io/issues/5236>`_, `#5262 <https://pulp.plan.io/issues/5262>`_, `#5332 <https://pulp.plan.io/issues/5332>`_, `#5333 <https://pulp.plan.io/issues/5333>`_


----


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
