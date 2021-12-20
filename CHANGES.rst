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

0.11.1 (2021-12-20)
===================

Misc
----

- `#774 <https://github.com/pulp/pulp_ansible/issues/774>`_


----


0.11.0 (2021-12-15)
===================

Features
--------

- Added ability to sync only metadata from a Git remote. This is a tech preview feature. The
  functionality may change in the future.
  `#744 <https://github.com/pulp/pulp_ansible/issues/744>`_
- Syncing now excludes collection versions found at ``/excludes/`` endpoint of remote.
  `#750 <https://github.com/pulp/pulp_ansible/issues/750>`_
- Added a Git Remote that is used to sync content from Git repositories. This is a tech preview
  feature. The functionality may change in the future.
  `#751 <https://github.com/pulp/pulp_ansible/issues/751>`_
- Added ability to sync collections using GitRemote. This is a tech preview feature. The
  functionality may change in the future.
  `#752 <https://github.com/pulp/pulp_ansible/issues/752>`_
- Use ``shared_resources`` in tasks where appropriate.
  `#753 <https://github.com/pulp/pulp_ansible/issues/753>`_


Bugfixes
--------

- Case-insensitive search for the ``owner__username`` and role ``name`` fields in the pulp_ansible role view (same as on galaxy.ansible.com).
  `#747 <https://github.com/pulp/pulp_ansible/issues/747>`_


----


0.10.1 (2021-10-05)
===================

Bugfixes
--------

- Added a better error message when trying to sync a missing collection using V3 endpoints.
  `#9404 <https://pulp.plan.io/issues/9404>`_
- Ensure deprecation status is in sync with the remote
  `#9442 <https://pulp.plan.io/issues/9442>`_
- Fixed optimized mirror syncs erroneously removing all content in the repository.
  `#9476 <https://pulp.plan.io/issues/9476>`_
- Changed the use of ``dispatch`` to match the signature from pulpcore>=3.15.
  `#9483 <https://pulp.plan.io/issues/9483>`_


Misc
----

- `#9368 <https://pulp.plan.io/issues/9368>`_


----


0.10.0 (2021-08-31)
===================

Features
--------

- Made deprecation exportable/importable
  `#8205 <https://pulp.plan.io/issues/8205>`_


Bugfixes
--------

- Fixed bug where sync tasks would open a lot of DB connections.
  `#9260 <https://pulp.plan.io/issues/9260>`_


Deprecations and Removals
-------------------------

- Turned collection deprecation status into a content.

  .. warning::

   Current deprecation history will be lost, only accounting for
   the latest repository version.

  `#8205 <https://pulp.plan.io/issues/8205>`_
- Dropped support for Python 3.6 and 3.7. pulp_ansible now supports Python 3.8+.
  `#9034 <https://pulp.plan.io/issues/9034>`_


Misc
----

- `#9119 <https://pulp.plan.io/issues/9119>`_


----


0.9.1 (2021-08-25)
==================

Bugfixes
--------

- Improved performance on reporting progress on parsing collection metadata
  `#9137 <https://pulp.plan.io/issues/9137>`_
- Ensure galaxy-importer is used when uploading collections
  `#9220 <https://pulp.plan.io/issues/9220>`_


Misc
----

- `#9250 <https://pulp.plan.io/issues/9250>`_


----


0.9.0 (2021-07-21)
==================

Bugfixes
--------

- Renaming bindings to be compatible with pulpcore >= 3.14
  `#8971 <https://pulp.plan.io/issues/8971>`_


Misc
----

- `#8882 <https://pulp.plan.io/issues/8882>`_


----


0.8.1 (2021-07-21)
==================

Bugfixes
--------

- Fixed an error message which indicated that the remote url was invalid when in fact the requirements
  source url was invalid.
  `#8957 <https://pulp.plan.io/issues/8957>`_
- Use proxy auth credentials of a Remote when syncing content.
  `#9075 <https://pulp.plan.io/issues/9075>`_


Misc
----

- `#9006 <https://pulp.plan.io/issues/9006>`_


----


0.8.0 (2021-06-01)
Features
--------

- Pulp Ansible can now sync collection dependencies by setting the ``sync_dependencies`` option for ``CollectionRemote`` objects.
  (By default set to true)
  `#7751 <https://pulp.plan.io/issues/7751>`_
- Enabled pulp_label support for AnsibleDistributions
  `#8441 <https://pulp.plan.io/issues/8441>`_
- Provide backend storage url to galaxy-importer on collection import.
  `#8486 <https://pulp.plan.io/issues/8486>`_


Bugfixes
--------

- `/collection_versions/all/` endpoint is now streamed to alleviate timeout issues
  `#8439 <https://pulp.plan.io/issues/8439>`_
- V3 sync now properly waits for async task completion
  `#8442 <https://pulp.plan.io/issues/8442>`_
- Remove scheme from apache snippet
  `#8572 <https://pulp.plan.io/issues/8572>`_
- Fix collections endpoint for collections named "api"
  `#8587 <https://pulp.plan.io/issues/8587>`_
- Fix requirements.yml parser for pinned collection version
  `#8627 <https://pulp.plan.io/issues/8627>`_
- Fixed dependency syncing slowing down from excessive task creation
  `#8639 <https://pulp.plan.io/issues/8639>`_
- Updated api lengths for collection version fields to match db model lengths.
  `#8649 <https://pulp.plan.io/issues/8649>`_
- Optimized unpaginated collection_versions endpoint
  `#8746 <https://pulp.plan.io/issues/8746>`_


Improved Documentation
----------------------

- Fixed broken link on client bindings page
  `#8298 <https://pulp.plan.io/issues/8298>`_


Misc
----

- `#8589 <https://pulp.plan.io/issues/8589>`_


----


0.7.1 (2021-03-04)
==================

Bugfixes
--------

- Removing ``manifest`` and ``files`` from metadata endpoints.
  `#8264 <https://pulp.plan.io/issues/8264>`_
- Fix V3 collection list endpoint when repository is empty
  `#8276 <https://pulp.plan.io/issues/8276>`_
- Use DRF token when no ``auth_url`` is provided
  `#8290 <https://pulp.plan.io/issues/8290>`_
- Fixed bug where rate limit wasn't being honored.
  `#8300 <https://pulp.plan.io/issues/8300>`_


----


0.6.2 (2021-03-03)
==================

Bugfixes
--------

- Use DRF token when no ``auth_url`` is provided
  `#8290 <https://pulp.plan.io/issues/8290>`_


----


0.5.7 (2021-03-03)
==================

Bugfixes
--------

- Use DRF token when no ``auth_url`` is provided
  `#8290 <https://pulp.plan.io/issues/8290>`_


----


0.7.0 (2021-02-11)
==================

Features
--------

- Ansible export/import is now available as a tech preview feature
  `#6738 <https://pulp.plan.io/issues/6738>`_
- Expose MANIFEST.json and FILES.json at CollectionVersion endpoint
  `#7572 <https://pulp.plan.io/issues/7572>`_
- Introduce a new ``v3/`` endpoint returning publication time
  `#7939 <https://pulp.plan.io/issues/7939>`_
- Introduces a new ``v3/collections/all/`` endpoint returning all collections unpaginated.
  `#7940 <https://pulp.plan.io/issues/7940>`_
- Introduces a new ``v3/collection_versions/all/`` endpoint returning all collections versions
  unpaginated.
  `#7941 <https://pulp.plan.io/issues/7941>`_
- Improve sync performance with no-op when possible. To disable the no-op optimization use the
  ``optimize=False`` option on the ``sync`` call.
  `#7942 <https://pulp.plan.io/issues/7942>`_
- Adds the ``requires_ansible`` attribute to the Galaxy V3 CollectionVersion APIs.
  This documents the version of Ansible required to use the collection.
  `#7949 <https://pulp.plan.io/issues/7949>`_
- Field ``updated_at`` from Galaxy v3 Collections endpoint using latest instead of highest version
  `#8012 <https://pulp.plan.io/issues/8012>`_
- Efficient sync with unpaginated metadata endpoints if they are available.
  `#8177 <https://pulp.plan.io/issues/8177>`_


Bugfixes
--------

- Make collection namespace max_length consistent in models
  `#8078 <https://pulp.plan.io/issues/8078>`_


Improved Documentation
----------------------

- Move official docs site to https://docs.pulpproject.org/pulp_ansible/.
  `#7926 <https://pulp.plan.io/issues/7926>`_
- Updated Roles and Collections workflows to use Pulp-CLI commands
  `#8076 <https://pulp.plan.io/issues/8076>`_


Misc
----

- `#8216 <https://pulp.plan.io/issues/8216>`_


----


0.6.1 (2021-01-15)
==================

Bugfixes
--------

- Allow updating ``auth_url`` on CollectionRemote when ``token`` is already set
  `#7957 <https://pulp.plan.io/issues/7957>`_
- Fixed create_task calls for Python 3.6 in collections tasks
  `#8098 <https://pulp.plan.io/issues/8098>`_


----


0.6.0 (2020-12-01)
==================

Features
--------

- Enable filter by name/namespace on Collections V3 endpoint
  `#7873 <https://pulp.plan.io/issues/7873>`_


Bugfixes
--------

- Allows a requirements.yml collection version specification to be respected during sync.
  `#7739 <https://pulp.plan.io/issues/7739>`_
- Allow requirements.yml with different sources to sync correctly.
  `#7741 <https://pulp.plan.io/issues/7741>`_
- Increased collection tag field length from 32 to 64, which allows sync to work for longer tag names
  used on galaxy.ansible.com.
  `#7827 <https://pulp.plan.io/issues/7827>`_


Misc
----

- `#7777 <https://pulp.plan.io/issues/7777>`_


----


0.5.6 (2021-01-12)
==================

Bugfixes
--------

- Fixed v3 schema pagination to match OpenAPI standard
  `#8037 <https://pulp.plan.io/issues/8037>`_
- Fix collection version comparison on re-syncs
  `#8039 <https://pulp.plan.io/issues/8039>`_
- Enable proxy on token refresh requests
  `#8051 <https://pulp.plan.io/issues/8051>`_


----


0.5.5 (2020-12-11)
==================

Bugfixes
--------

- Field ``updated_at`` from Galaxy v3 Collections endpoint using highest version
  `#7990 <https://pulp.plan.io/issues/7990>`_


----


0.5.4 (2020-12-04)
==================

Bugfixes
--------

- Increase interval between requests when token is required
  `#7929 <https://pulp.plan.io/issues/7929>`_


----


0.5.3 (2020-12-04)
==================

Bugfixes
--------

- Avoid rate limiting by slowing down sync when token is required
  `#7917 <https://pulp.plan.io/issues/7917>`_


----


0.5.2 (2020-11-19)
==================

Bugfixes
--------

- Improve MANIFEST.json handling and provide better error message
  `#5745 <https://pulp.plan.io/issues/5745>`_
- Ensure that when creating a ``CollectionRemote`` you can use ``token`` without specifying ``auth_url``
  `#7821 <https://pulp.plan.io/issues/7821>`_
- Fix version comparisons during sync and upload when comparing the same version with different build
  numbers.
  `#7826 <https://pulp.plan.io/issues/7826>`_
- Stop making requests to docs-blob endpoint on Galaxy v2
  `#7830 <https://pulp.plan.io/issues/7830>`_
- Avoid to download docs-blob when content is already saved
  `#7831 <https://pulp.plan.io/issues/7831>`_
- Ensure deprecation status is synced even when no content changes
  `#7834 <https://pulp.plan.io/issues/7834>`_
- Fix deprecation status update for pulp-ansible-client
  `#7871 <https://pulp.plan.io/issues/7871>`_
- Makes ``url`` optional when patching a collection remote
  `#7872 <https://pulp.plan.io/issues/7872>`_


----


0.5.1 (2020-11-09)
==================

Bugfixes
--------

- Token refresh happens when needed, not on every call.
  `#7643 <https://pulp.plan.io/issues/7643>`_
- Field ``updated_at`` from Galaxy v3 Collections endpoint using latest instead of highest version
  `#7775 <https://pulp.plan.io/issues/7775>`_
- Allow CollectionUploadViewSet subclass to set own serializer
  `#7788 <https://pulp.plan.io/issues/7788>`_
- Ensure that when creating a ``CollectionRemote`` with either a ``token`` or ``auth_url`` that you
  use both together.
  `#7802 <https://pulp.plan.io/issues/7802>`_


----


0.5.0 (2020-10-29)
==================

Features
--------

- Adds a new ``/pulp/api/v3/ansible/copy/`` endpoint allowing content to be copied from one
  ``AnsibleRepository`` version to a destination ``AnsibleRepository``.
  `#7621 <https://pulp.plan.io/issues/7621>`_


Bugfixes
--------

- Sync collection deprecation status
  `#7504 <https://pulp.plan.io/issues/7504>`_
- Supporting url formats that conform to ansible-galaxy cli (e.g. "https://galaxy.ansible.com" and
  "https://galaxy.ansible.com/api").
  `#7686 <https://pulp.plan.io/issues/7686>`_
- Fixed bug where only 10 collections were being synced in some cases
  `#7740 <https://pulp.plan.io/issues/7740>`_
- Fixed syncing with a default remote.
  `#7742 <https://pulp.plan.io/issues/7742>`_
- Increase the version size for ``CollectionVersions``.
  `#7745 <https://pulp.plan.io/issues/7745>`_
- Fixed bug where we didn't properly handle trailing slashes.
  `#7767 <https://pulp.plan.io/issues/7767>`_


Deprecations and Removals
-------------------------

- Remove 'certification' flag from CollectionVersion
  `#6715 <https://pulp.plan.io/issues/6715>`_
- Derive ANSIBLE_CONTENT_HOSTNAME from CONTENT_ORIGIN
  `#7368 <https://pulp.plan.io/issues/7368>`_
- Removing `deprecated` field from Collection
  `#7504 <https://pulp.plan.io/issues/7504>`_
- Url formats must conform to ansible-galaxy cli format (e.g. "https://galaxy.ansible.com" and
  "https://galaxy.ansible.com/api"). This means we no longer support urls such as
  "https://galaxy.ansible.com/api/v2/collections" or
  "https://galaxy.ansible.com/api/v2/collections/amazon/aws".
  `#7686 <https://pulp.plan.io/issues/7686>`_
- Galaxy URLs now require trailing slashes per the ansible-galaxy docs. Made an exception for
  "https://galaxy.ansible.com" since the ansible-galaxy CLI code does as well.
  `#7767 <https://pulp.plan.io/issues/7767>`_


----


0.4.3 (2020-11-04)
==================

Features
--------

- Allow CollectionUploadViewSet subclass to set own serializer
  `#7788 <https://pulp.plan.io/issues/7788>`_


----


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
