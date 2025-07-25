# Changelog

[//]: # (You should *NOT* be adding new change log entries to this file, this)
[//]: # (file is managed by towncrier. You *may* edit previous change logs to)
[//]: # (fix problems like typo corrections or such.)
[//]: # (To add a new change log entry, please see the contributing docs.)
[//]: # (WARNING: Don't drop the towncrier directive!)

[//]: # (towncrier release notes start)

## 0.27.1 (2025-07-15) {: #0.27.1 }

#### Bugfixes {: #0.27.1-bugfix }

- Fixed the sync pipeline to not manipulate the RepositoryContent table directly when undeprecating collections.

---

## 0.27.0 (2025-07-09) {: #0.27.0 }

#### Features {: #0.27.0-feature }

- Added support for the domains feature.
  [#1549](https://github.com/pulp/pulp_ansible/issues/1549)

#### Deprecations and Removals {: #0.27.0-removal }

- This is the second part of the tags db reorganization.

  This release contains a migration that allows zero downtime upgrades only from version 0.26.

---

## 0.26.0 (2025-05-27) {: #0.26.0 }

#### Features {: #0.26.0-feature }

- Added a migration to prepare moving tags into an array field on collection versions.

  The second part of the migration will be shipped in the next release to keep the process zero downtime safe.

#### Bugfixes {: #0.26.0-bugfix }

- Fixed broken collection import logs.
- Made collection sync slightly more resiliant in face of missing "next" links.

#### Deprecations and Removals {: #0.26.0-removal }

- Remove the `is_highest` field from CollectionVersion table.
  [#1550](https://github.com/pulp/pulp_ansible/issues/1550)

---

## 0.25.1 (2025-05-06) {: #0.25.1 }

#### Bugfixes {: #0.25.1-bugfix }

- Fixed broken collection import logs.
- Made collection sync slightly more resiliant in face of missing "next" links.

---

## 0.25.0 (2025-04-23) {: #0.25.0 }

#### Features {: #0.25.0-feature }

- Added namespace progress report.

#### Bugfixes {: #0.25.0-bugfix }

- Renamed duplicate 'Downloading Artifacts' sync progress report message to 'Downloading Docs Blob'.
  [#1369](https://github.com/pulp/pulp_ansible/issues/1369)
- Fixed a migration that was failing when upgrading on a system that was on 0.23.0 at one point in time.
  [#2118](https://github.com/pulp/pulp_ansible/issues/2118)
- Fixed deadlock when performing multiple syncs with similar collections.
  [#2131](https://github.com/pulp/pulp_ansible/issues/2131)
- Fixed optimization of fetching namespace logos during sync.
  [#2138](https://github.com/pulp/pulp_ansible/issues/2138)
- Added a workaround to the `CollectionVersionSearchListSerializer` to allow installing djangorestframework>=3.16.
- Added version constraint on djangorestframework to prevent an interference leading to a missing `repository_version` field in the openapi specification.
- Fixed a bug in the git sync caused by a bad serialization after pulpcore 3.73.0.
- Fixed namespace avatar download log.

---

## 0.24.7 (2025-07-15) {: #0.24.7 }

#### Bugfixes {: #0.24.7-bugfix }

- Fixed the sync pipeline to not manipulate the RepositoryContent table directly when undeprecating collections.

---

## 0.24.6 (2025-04-23) {: #0.24.6 }

#### Features {: #0.24.6-feature }

- Added namespace progress report.

#### Bugfixes {: #0.24.6-bugfix }

- Fixed optimization of fetching namespace logos during sync.
  [#2138](https://github.com/pulp/pulp_ansible/issues/2138)

---

## 0.24.5 (2025-04-15) {: #0.24.5 }

#### Bugfixes {: #0.24.5-bugfix }

- Fixed namespace avatar download log.

---

## 0.24.4 (2025-04-07) {: #0.24.4 }

#### Bugfixes {: #0.24.4-bugfix }

- Added a workaround to the `CollectionVersionSearchListSerializer` to allow installing djangorestframework>=3.16.

---

## 0.24.3 (2025-04-03) {: #0.24.3 }

#### Bugfixes {: #0.24.3-bugfix }

- Added version constraint on djangorestframework to prevent an interference leading to a missing `repository_version` field in the openapi specification.

---

## 0.24.2 (2025-03-12) {: #0.24.2 }

#### Bugfixes {: #0.24.2-bugfix }

- Fixed deadlock when performing multiple syncs with similar collections.
  [#2131](https://github.com/pulp/pulp_ansible/issues/2131)
- Fixed a bug in the git sync caused by a bad serialization after pulpcore 3.73.0.

---

## 0.24.1 (2025-02-18) {: #0.24.1 }

#### Bugfixes {: #0.24.1-bugfix }

- Fixed a migration that was failing when upgrading on a system that was on 0.23.0 at one point in time.
  [#2118](https://github.com/pulp/pulp_ansible/issues/2118)

---

## 0.24.0 (2025-02-17) {: #0.24.0 }

#### Features {: #0.24.0-feature }

- CollectionVersion global uniqueness constraint is now its sha256 digest. Repository level uniqueness
  is still (namespace, name, version).
  [#1052](https://github.com/pulp/pulp_ansible/issues/1052)

#### Bugfixes {: #0.24.0-bugfix }

- Fixed a regression with migration 0056 failing on multiple null values on a unique constraint.
  [#2040](https://github.com/pulp/pulp_ansible/issues/2040)

#### Deprecations and Removals {: #0.24.0-removal }

- Added the final migration to make the sha256 of the collection version artifact the uniqueness
  constraint. This allows users to serve their own interpretation of the content in their private
  repositories.
  The migration will only succeed if all the content has been adjusted. To account for content that
  was not migrated by the migration shipped with 0.23.0, you can run the content repair command
  ``datarepair-ansible-collection-sha256`` prior to upgrading.
  This version removed the content repair command.
  [#1052](https://github.com/pulp/pulp_ansible/issues/1052)
- Rebased and squashed old migrations to prepare for pulpcore 3.70 compatibility.
  [#2062](https://github.com/pulp/pulp_ansible/issues/2062)

#### Misc {: #0.24.0-misc }

- [#2081](https://github.com/pulp/pulp_ansible/issues/2081), [#2083](https://github.com/pulp/pulp_ansible/issues/2083)

---

## 0.23.1 (2024-11-22) {: #0.23.1 }

#### Bugfixes {: #0.23.1-bugfix }

- Fixed a regression with migration 0056 failing on multiple null values on a unique constraint.
  [#2040](https://github.com/pulp/pulp_ansible/issues/2040)

---

## YANKED 0.23.0 (2024-11-11) {: #0.23.0 }

Yank reason: Contains a bad migration

#### Features {: #0.23.0-feature }

- Added sha256 to collection versions.
  This is the first part of a change to make this field the uniqueness constraint in the database.
  The `datarepair-ansible-collection-sha256` management command is provided to prepare for the next release bringing the second and final step.

#### Bugfixes {: #0.23.0-bugfix }

- Fixed some 500 errors when browsing the Galaxy API.
  [#galaxy500s](https://github.com/pulp/pulp_ansible/issues/galaxy500s)
- Cast the content object to a collectionversion before setting the rebuild metadata.
  [#1921](https://github.com/pulp/pulp_ansible/issues/1921)
- Fixed a bug hitting a db restriction with `is_highest` on import.
  [#1986](https://github.com/pulp/pulp_ansible/issues/1986)
- Use the highest collection version to reflect a collection's update_at timestamp.
  [#2000](https://github.com/pulp/pulp_ansible/issues/2000)
- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).
- Fixed the openapi spec for the collection version search.

#### Deprecations and Removals {: #0.23.0-removal }

- Removed `is_highest` from collection versions.
  [#1986](https://github.com/pulp/pulp_ansible/issues/1986)
- Removed the `is_highest` attribute on CollectionVersion.

---

## 0.22.6 (2025-05-06) {: #0.22.6 }

#### Bugfixes {: #0.22.6-bugfix }

- Made collection sync slightly more resiliant in face of missing "next" links.

---

## 0.22.5 (2025-04-23) {: #0.22.5 }

#### Features {: #0.22.5-feature }

- Added namespace progress report.

#### Bugfixes {: #0.22.5-bugfix }

- Fixed optimization of fetching namespace logos during sync.
  [#2138](https://github.com/pulp/pulp_ansible/issues/2138)

---

## 0.22.4 (2025-03-12) {: #0.22.4 }

#### Bugfixes {: #0.22.4-bugfix }

- Fixed deadlock when performing multiple syncs with similar collections.
  [#2131](https://github.com/pulp/pulp_ansible/issues/2131)

---

## 0.22.3 (2024-11-12) {: #0.22.3 }

#### Bugfixes {: #0.22.3-bugfix }

- Fixed some 500 errors when browsing the Galaxy API.
  [#galaxy500s](https://github.com/pulp/pulp_ansible/issues/galaxy500s)

---

## 0.22.2 (2024-10-29) {: #0.22.2 }

#### Bugfixes {: #0.22.2-bugfix }

- Set `is_highest` to `False` before importing a collection version to prevent conflicts.
  [#1986](https://github.com/pulp/pulp_ansible/issues/1986)
- Use the highest collection version to reflect a collection's update_at timestamp.
  [#2000](https://github.com/pulp/pulp_ansible/issues/2000)
- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).

---

## 0.22.1 (2024-07-22) {: #0.22.1 }


#### Bugfixes {: #0.22.1-bugfix }

- Cast the content object to a collectionversion before setting the rebuild metadata.
  [#1921](https://github.com/pulp/pulp_ansible/issues/1921)
- Fixed the openapi spec for the collection version search.

---

## 0.22.0 (2024-06-20) {: #0.22.0 }


#### Bugfixes {: #0.22.0-bugfix }

- Fixed syncing progress report, `Parsing CollectionVersion Metadata`, total count when using `signed_only=True`.
  [#1608](https://github.com/pulp/pulp_ansible/issues/1608)
- Duplicate Collection uploads no longer return 400s.
  [#1691](https://github.com/pulp/pulp_ansible/issues/1691)
- Fixed AnsibleNamespaceMetadata not being exported.
  [#1764](https://github.com/pulp/pulp_ansible/issues/1764)
- Fixed a bug failing sync on namespace metadata when avatar_sha256 is missing.
  [#1772](https://github.com/pulp/pulp_ansible/issues/1772)
- Add ansible hostname to API v3 cache key
  [#1833](https://github.com/pulp/pulp_ansible/issues/1833)
- Fixed import failing to associate signatures and marks with their collection version.
  [#1836](https://github.com/pulp/pulp_ansible/issues/1836)
- Fixed sync failing on undownloadable namespace avatars.
  [#1868](https://github.com/pulp/pulp_ansible/issues/1868)
- Changed avatar download to allow graceful failure on mismatching image checksum.
- Fixed the api for direct creation of collection_deprecated content.

#### Improved Documentation {: #0.22.0-doc }

- Convert docs to new style.
  [#1754](https://github.com/pulp/pulp_ansible/issues/1754)

#### Deprecations and Removals {: #0.22.0-removal }

- Removed the galaxy v2 apis. The v3 apis should be used instead.
  [#691](https://github.com/pulp/pulp_ansible/issues/691)
- Bumped `pulpcore` requirement to `>=3.39.0` and dropped `python 3.8` support.

---

## 0.21.13 (2025-05-06) {: #0.21.13 }

#### Bugfixes {: #0.21.13-bugfix }

- Made collection sync slightly more resiliant in face of missing "next" links.

---

## 0.21.12 (2025-04-23) {: #0.21.12 }

#### Features {: #0.21.12-feature }

- Added namespace progress report.

#### Bugfixes {: #0.21.12-bugfix }

- Fixed optimization of fetching namespace logos during sync.
  [#2138](https://github.com/pulp/pulp_ansible/issues/2138)

---

## 0.21.11 (2025-04-15) {: #0.21.11 }

#### Bugfixes {: #0.21.11-bugfix }

- Fixed namespace avatar download log.

---

## 0.21.10 (2025-03-18) {: #0.21.10 }

#### Bugfixes {: #0.21.10-bugfix }

- Fixed deadlock when performing multiple syncs with similar collections.
  [#2131](https://github.com/pulp/pulp_ansible/issues/2131)

---

## 0.21.9 (2024-10-29) {: #0.21.9 }

#### Bugfixes {: #0.21.9-bugfix }

- Set `is_highest` to `False` before importing a collection version to prevent conflicts.
  [#1986](https://github.com/pulp/pulp_ansible/issues/1986)
- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).

---

## 0.21.8 (2024-08-14) {: #0.21.8 }

#### Bugfixes {: #0.21.8-bugfix }

- Fixed import failing to associate signatures and marks with their collection version.
  [#1836](https://github.com/pulp/pulp_ansible/issues/1836)

---

## 0.21.7 (2024-07-22) {: #0.21.7 }


#### Bugfixes {: #0.21.7-bugfix }

- Cast the content object to a collectionversion before setting the rebuild metadata.
  [#1921](https://github.com/pulp/pulp_ansible/issues/1921)
- Fixed the openapi spec for the collection version search.

---

## 0.21.6 (2024-05-29) {: #0.21.6 }

#### Bugfixes

-   Fixed sync failing on undownloadable namespace avatars.
    [#1868](https://github.com/pulp/pulp_ansible/issues/1868)

---

## 0.21.5 (2024-05-15) {: #0.21.5 }

No significant changes.

---

## 0.21.4 (2024-05-07) {: #0.21.4 }

#### Bugfixes

-   Add ansible hostname to API v3 cache key
    [#1833](https://github.com/pulp/pulp_ansible/issues/1833)

---

## 0.21.3 (2024-02-28) {: #0.21.3 }

#### Bugfixes

-   Fixed AnsibleNamespaceMetadata not being exported.
    [#1764](https://github.com/pulp/pulp_ansible/issues/1764)
-   Fixed a bug failing sync on namespace metadata when avatar_sha256 is missing.
    [#1772](https://github.com/pulp/pulp_ansible/issues/1772)
-   Changed avatar download to allow graceful failure on mismatching image checksum.

---

## 0.21.2 (2024-02-26) {: #0.21.2 }

No significant changes.

---

## 0.21.1 (2023-12-12) {: #0.21.1 }

#### Bugfixes

-   Duplicate Collection uploads no longer return 400s.
    [#1691](https://github.com/pulp/pulp_ansible/issues/1691)

---

## 0.21.0 (2023-11-03) {: #0.21.0 }

#### Features

-   Added pulpcore 3.40 compatibility.
-   Display the `count` attribute in the tags of collections.
    [#1612](https://github.com/pulp/pulp_ansible/issues/1612)

#### Bugfixes

-   Ignore the "users" field in namespace data during sync.
    [#1598](https://github.com/pulp/pulp_ansible/issues/1598)
-   Fixed highest version calculation failing when versions of a collection were created out of order.
    [#1623](https://github.com/pulp/pulp_ansible/issues/1623)

---

## 0.20.12 (2025-05-06) {: #0.20.12 }

#### Bugfixes {: #0.20.12-bugfix }

- Made collection sync slightly more resiliant in face of missing "next" links.

---

## 0.20.11 (2025-04-23) {: #0.20.11 }

#### Features {: #0.20.11-feature }

- Added namespace progress report.

#### Bugfixes {: #0.20.11-bugfix }

- Fixed optimization of fetching namespace logos during sync.
  [#2138](https://github.com/pulp/pulp_ansible/issues/2138)

---

## 0.20.10 (2025-01-16) {: #0.20.10 }

No significant changes.

---

## 0.20.9 (2024-10-31) {: #0.20.9 }

#### Bugfixes {: #0.20.9-bugfix }

- Set `is_highest` to `False` before importing a collection version to prevent conflicts.
  [#1986](https://github.com/pulp/pulp_ansible/issues/1986)
- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).

---

## 0.20.8 (2024-07-22) {: #0.20.8 }


#### Bugfixes {: #0.20.8-bugfix }

- Cast the content object to a collectionversion before setting the rebuild metadata.
  [#1921](https://github.com/pulp/pulp_ansible/issues/1921)
- Fixed the openapi spec for the collection version search.

---

## 0.20.7 (2024-05-29) {: #0.20.7 }

#### Bugfixes

-   Fixed sync failing on undownloadable namespace avatars.
    [#1868](https://github.com/pulp/pulp_ansible/issues/1868)

---

## 0.20.6 (2024-05-15) {: #0.20.6 }

#### Bugfixes

-   Fixed import failing to associate signatures and marks with their collection version.
    [#1836](https://github.com/pulp/pulp_ansible/issues/1836)

---

## 0.20.5 (2024-04-11) {: #0.20.5 }

No significant changes.

---

## 0.20.4 (2024-02-28) {: #0.20.4 }

#### Bugfixes

-   Fixed AnsibleNamespaceMetadata not being exported.
    [#1764](https://github.com/pulp/pulp_ansible/issues/1764)
-   Fixed a bug failing sync on namespace metadata when avatar_sha256 is missing.
    [#1772](https://github.com/pulp/pulp_ansible/issues/1772)
-   Changed avatar download to allow graceful failure on mismatching image checksum.

---

## 0.20.3 (2023-12-12) {: #0.20.3 }

#### Bugfixes

-   Duplicate Collection uploads no longer return 400s.
    [#1691](https://github.com/pulp/pulp_ansible/issues/1691)

---

## 0.20.2 (2023-10-23) {: #0.20.2 }

#### Bugfixes

-   Fixed highest version calculation failing when versions of a collection were created out of order.
    [#1623](https://github.com/pulp/pulp_ansible/issues/1623)

---

## 0.20.1 (2023-10-03) {: #0.20.1 }

#### Bugfixes

-   Ignore the "users" field in namespace data during sync.
    [#1598](https://github.com/pulp/pulp_ansible/issues/1598)

---

## 0.20.0 (2023-09-26) {: #0.20.0 }

#### Features

-   Added settings `ANSIBLE_AUTHENTICATION_CLASSES` and `ANSIBLE_PERMISSION_CLASSES` to allow for
    customizing Galaxy authentication and authorization separate from Pulp APIs.
    [#1555](https://github.com/pulp/pulp_ansible/issues/1555)
-   Adjusted default access policies for new labels api.
    [#1568](https://github.com/pulp/pulp_ansible/issues/1568)

#### Bugfixes

-   Fixed ordering by version in the `/ansible/search/collection-versions/` endpoint.
    [#1516](https://github.com/pulp/pulp_ansible/issues/1516)
-   Stopped collection sync from failing if a namespace's avatar url was unreachable.
    [#1543](https://github.com/pulp/pulp_ansible/issues/1543)
-   Fixed a sporadic sync error when re-syncing a repository with new collection versions.
    [#1547](https://github.com/pulp/pulp_ansible/issues/1547)
-   Prevented a race condition that lead to contraint violations when calculating the highest version of a collection.
    [#1571](https://github.com/pulp/pulp_ansible/issues/1571)

#### Misc

-   [#1506](https://github.com/pulp/pulp_ansible/issues/1506)

---

## 0.19.0 (2023-07-20) {: #0.19.0 }

#### Features

-   Exposes collection download count in the api.
    Download count controlled by new setting ANSIBLE_COLLECT_DOWNLOAD_COUNT.
    [#1478](https://github.com/pulp/pulp_ansible/issues/1478)

#### Bugfixes

-   Fixed the migration 0030 in face of collections without runtime.yml.
    [#1480](https://github.com/pulp/pulp_ansible/issues/1480)
-   Wrapped db writes with try/except for collection download logs with read-only databases.
    [#1491](https://github.com/pulp/pulp_ansible/issues/1491)
-   Fixed updated namespacemetadata in x-repo search indexing.
    [#1494](https://github.com/pulp/pulp_ansible/issues/1494)

---

## 0.18.4 (2025-02-17) {: #0.18.4 }

No significant changes.

---

## 0.18.3 (2024-10-31) {: #0.18.3 }

#### Bugfixes {: #0.18.3-bugfix }

- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).
- Fixed the openapi spec for the collection version search.

---

## 0.18.2 (2023-10-03) {: #0.18.2 }

#### Bugfixes

-   Ignore the "users" field in namespace data during sync.
    [#1598](https://github.com/pulp/pulp_ansible/issues/1598)

---

## 0.18.1 (2023-09-21) {: #0.18.1 }

#### Features

-   Added settings `ANSIBLE_AUTHENTICATION_CLASSES` and `ANSIBLE_PERMISSION_CLASSES` to allow for
    customizing Galaxy authentication and authorization separate from Pulp APIs.
    [#1555](https://github.com/pulp/pulp_ansible/issues/1555)

---

## 0.18.0 (2023-05-25) {: #0.18.0 }

#### Features

-   Updated compatibility for pulpcore 3.25 and Django 4.2.
    [#1462](https://github.com/pulp/pulp_ansible/issues/1462)

#### Bugfixes

-   Reduce fetched fields in cv list endpoint to prevent oomkill.
    [#1433](https://github.com/pulp/pulp_ansible/issues/1433)
-   Fix traceback when publishing a collection to the v2 API endpoint
    [#1441](https://github.com/pulp/pulp_ansible/issues/1441)
-   Fixed several bugs in the galaxy v2 API related to generating URLs for various collection resources.
    [#1452](https://github.com/pulp/pulp_ansible/issues/1452)
-   Increase collectionversion search index build speeds.
    [#1467](https://github.com/pulp/pulp_ansible/issues/1467)

---

## 0.17.5 (2023-10-03) {: #0.17.5 }

#### Bugfixes

-   Ignore the "users" field in namespace data during sync.
    [#1598](https://github.com/pulp/pulp_ansible/issues/1598)

---

## 0.17.4 (2023-08-10) {: #0.17.4 }

#### Bugfixes

-   Stopped collection sync from failing if a namespace's avatar url was unreachable.
    [#1543](https://github.com/pulp/pulp_ansible/issues/1543)
-   Fixed a sporadic sync error when re-syncing a repository with new collection versions.
    [#1547](https://github.com/pulp/pulp_ansible/issues/1547)

---

## 0.17.3 (2023-07-05) {: #0.17.3 }

#### Bugfixes

-   Fixed updated namespacemetadata in x-repo search indexing.
    [#1494](https://github.com/pulp/pulp_ansible/issues/1494)

---

## 0.17.2 (2023-05-30) {: #0.17.2 }

#### Bugfixes

-   Fixed several bugs in the galaxy v2 API related to generating URLs for various collection resources.
    [#1452](https://github.com/pulp/pulp_ansible/issues/1452)
-   Increase collectionversion search index build speeds.
    [#1467](https://github.com/pulp/pulp_ansible/issues/1467)

---

## 0.17.1 (2023-05-09) {: #0.17.1 }

#### Bugfixes

-   Reduce fetched fields in cv list endpoint to prevent oomkill.
    [#1433](https://github.com/pulp/pulp_ansible/issues/1433)
-   Fix traceback when publishing a collection to the v2 API endpoint
    [#1441](https://github.com/pulp/pulp_ansible/issues/1441)

---

## 0.17.0 (2023-03-30) {: #0.17.0 }

#### Features

-   Added Namespace metadata content model and Galaxy endpoints v3/namespaces/ & [v3/plugin/ansible/content/<base_path>/namespaces/]{.title-ref}.

    Added ability to sync Namespaces during Collection syncs.
    [#735](https://github.com/pulp/pulp_ansible/issues/735)

-   Add a cross repository collection version index for fast searching and filtering.
    [#739](https://github.com/pulp/pulp_ansible/issues/739)

-   Added "total" count on "sync.parsing.metadata" progress report.
    [#1219](https://github.com/pulp/pulp_ansible/issues/1219)

-   Added Role Based Access Control.
    New default roles (creator, owner, viewer) have been added for `AnsibleRepository`, `AnsibleDistribution`,
    `CollectionRemote`, `RoleRemote`, and `GitRemote`.
    New detail role management endpoints (`my_permissions`, `list_roles`, `add_role`,
    `remove_role`) have been added to `AnsibleRepository`, `AnsibleDistribution`, `CollectionRemote`,
    `GitRemote`, and `RoleRemote`.
    [#1290](https://github.com/pulp/pulp_ansible/issues/1290)

-   Add CollectionVersionMark as a content
    [#1325](https://github.com/pulp/pulp_ansible/issues/1325)

-   Added `last_sync_task` field to `CollectionRemote` and `AnsibleRepository`.
    Added filtering by `url` in `CollectionRemote`.
    [#1344](https://github.com/pulp/pulp_ansible/issues/1344)

-   Created POST `{repo_href}/copy_collection_version/` and POST
    `{repo_href}/copy_collection_version/` API endpoints which
    allow for copying and moving collections between repos.
    [#1394](https://github.com/pulp/pulp_ansible/issues/1394)

#### Bugfixes

-   GitRemotes can now be attached to an AnsibleRepository.
    [#1140](https://github.com/pulp/pulp_ansible/issues/1140)
-   Fixed a 500 server error in the `repositories/ansible/ansible/{repository_pk}/versions/{number}/rebuild_metadata/` endpoint.
    [#1322](https://github.com/pulp/pulp_ansible/issues/1322)
-   Pinned the dependency upper bound on setuptools to <66.2.0. Newer versions introduce stricter
    PEP-440 parsing.
    [#1340](https://github.com/pulp/pulp_ansible/issues/1340)
-   Fixed duplicate operationIDs in Galaxy V1 & V2 API endpoint schemas.
    [#1356](https://github.com/pulp/pulp_ansible/issues/1356)
-   Fix exclude list when syncing from galaxy_ng.
    [#1381](https://github.com/pulp/pulp_ansible/issues/1381)
-   Fixed broken sync form servers without signatures or marks.
    [#1387](https://github.com/pulp/pulp_ansible/issues/1387)
-   Fix 404 on collection detail routing for collections with a name of "collections".
    [#1388](https://github.com/pulp/pulp_ansible/issues/1388)
-   Pre-release collection versions should only be higher than stable releases when none exist.
    [#1391](https://github.com/pulp/pulp_ansible/issues/1391)
-   Selectively delete indexes for content no longer in the repo.
    [#1396](https://github.com/pulp/pulp_ansible/issues/1396)

#### Improved Documentation

-   Fixed linebreak issues in remote workflow cli examples.
    [#1328](https://github.com/pulp/pulp_ansible/issues/1328)

#### Misc

-   [#1349](https://github.com/pulp/pulp_ansible/issues/1349)

---

## 0.16.7 (2025-03-12) {: #0.16.7 }

No significant changes.

---

## 0.16.6 (2025-01-16) {: #0.16.6 }

No significant changes.

---

## 0.16.5 (2024-10-31) {: #0.16.5 }

#### Bugfixes {: #0.16.5-bugfix }

- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).

---

## 0.16.4 (2024-09-25) {: #0.16.4 }

#### Bugfixes {: #0.16.4-bugfix }

- Pre-release collection versions should only be higher than stable releases when none exist.
  [#1391](https://github.com/pulp/pulp_ansible/issues/1391)
- Fixed a sporadic sync error when re-syncing a repository with new collection versions.
  [#1547](https://github.com/pulp/pulp_ansible/issues/1547)

---

## 0.16.3 (2024-05-15) {: #0.16.3 }

#### Bugfixes

-   Fixed import failing to associate signatures and marks with their collection version.
    [#1836](https://github.com/pulp/pulp_ansible/issues/1836)

---

## 0.16.2 (2023-12-14) {: #0.16.2 }

#### Bugfixes

-   Fix exclude list when syncing from galaxy_ng.
    [#1381](https://github.com/pulp/pulp_ansible/issues/1381)
-   Fix traceback when publishing a collection to the v2 API endpoint
    [#1441](https://github.com/pulp/pulp_ansible/issues/1441)

---

## 0.16.1 (2023-02-23) {: #0.16.1 }

#### Bugfixes

-   Removed unused dependency on packaging.
    [#1366](https://github.com/pulp/pulp_ansible/issues/1366)

#### Improved Documentation

-   Fixed linebreak issues in remote workflow cli examples.
    [#1328](https://github.com/pulp/pulp_ansible/issues/1328)

#### Misc

-   [#1349](https://github.com/pulp/pulp_ansible/issues/1349)

---

## 0.16.0 (2022-12-01) {: #0.16.0 }

#### Features

-   An existing artifact or upload object can now be used to create a Collection.
    [#1175](https://github.com/pulp/pulp_ansible/issues/1175)

#### Bugfixes

-   Properly return 400 error when trying to create/upload a duplicate Collection.
    [#1175](https://github.com/pulp/pulp_ansible/issues/1175)
-   Fixed unnecessary creation of intermediate repository versions when performing a collection delete.
    [#1274](https://github.com/pulp/pulp_ansible/issues/1274)
-   Limit search_vector to only tags for the collectionversion instead of all collectionversions.
    [#1278](https://github.com/pulp/pulp_ansible/issues/1278)

#### Deprecations and Removals

-   Renamed CollectionVersion upload fields [namespace, name, version] to [expected]()[namespace, name, version].

    Deprecated /ansible/collections/ upload endpoint. Use /pulp/api/v3/content/ansible/collection_versions/ instead.

    Deprecated Galaxy V2 Collection upload endpoint. Use Galaxy V3 Collection Artifact upload endpoint instead.
    [#1176](https://github.com/pulp/pulp_ansible/issues/1176)

#### Misc

-   [#1273](https://github.com/pulp/pulp_ansible/issues/1273)

---

## 0.15.6 (2024-10-31) {: #0.15.6 }

#### Bugfixes {: #0.15.6-bugfix }

- Fixed the JSONField specification so it doesn't break ruby bindings.
  See context [here](https://github.com/pulp/pulp_rpm/issues/3639).

---

## 0.15.5 (2024-05-15) {: #0.15.5 }

#### Bugfixes

-   Fixed import failing to associate signatures and marks with their collection version.
    [#1836](https://github.com/pulp/pulp_ansible/issues/1836)

---

## 0.15.4 (2023-12-14) {: #0.15.4 }

#### Bugfixes

-   Fix exclude list when syncing from galaxy_ng.
    [#1381](https://github.com/pulp/pulp_ansible/issues/1381)

---

## 0.15.3 (2023-02-23) {: #0.15.3 }

#### Bugfixes

-   Removed unused dependency on packaging.
    [#1366](https://github.com/pulp/pulp_ansible/issues/1366)

#### Misc

-   [#1349](https://github.com/pulp/pulp_ansible/issues/1349)

---

## 0.15.2 (2023-02-03) {: #0.15.2 }

#### Bugfixes

-   Pinned the dependency upper bound on setuptools to <66.2.0. Newer versions introduce stricter
    PEP-440 parsing.
    [#1340](https://github.com/pulp/pulp_ansible/issues/1340)

---

## 0.15.1 (2023-01-20) {: #0.15.1 }

#### Improved Documentation

-   Fixed linebreak issues in remote workflow cli examples.
    [#1328](https://github.com/pulp/pulp_ansible/issues/1328)

#### Misc

-   [#1273](https://github.com/pulp/pulp_ansible/issues/1273)

---

## 0.15.0 (2022-09-21) {: #0.15.0 }

#### Features

-   Implement v3/plugin/client-configuration/ endpoint to communicate to the ansible galaxy client
    which distribution to use.
    [#740](https://github.com/pulp/pulp_ansible/issues/740)
-   Added modelresources for Pulp import/export of collection version signatures.
    [#844](https://github.com/pulp/pulp_ansible/issues/844)
-   Added CollectionDownloadLog table and logger.
    [#946](https://github.com/pulp/pulp_ansible/issues/946)
-   Added `rebuild_metadata` endpoint to ansible repositories and repository versions.
    [#1106](https://github.com/pulp/pulp_ansible/issues/1106)

#### Bugfixes

-   Fixed bug where Git Remote failed to clone git submodules when syncing a collection from a git
    repository.
    [#1065](https://github.com/pulp/pulp_ansible/issues/1065)
-   Add a gpgkey field to the ansible repository to ease verification of collection signatures.
    [#1086](https://github.com/pulp/pulp_ansible/issues/1086)
-   Fixed a bug where updating a CollectionRemote did not reset all repositories sync timestamp.
    [#1177](https://github.com/pulp/pulp_ansible/issues/1177)
-   Update the jsonschema requirements to not conflict with ansible-lint. Currently ansible-lint requires at least 4.9, so match that.
    [#1202](https://github.com/pulp/pulp_ansible/issues/1202)
-   Switched the attribute token on CollectionRemotes to be encrypted in the database and not to
    be exposed in the API.
    [#1221](https://github.com/pulp/pulp_ansible/issues/1221)

#### Deprecations and Removals

-   Removed `keyring` attribute from repositories in favor of `gpgkey`.
    [#1086](https://github.com/pulp/pulp_ansible/issues/1086)

#### Misc

-   [#1230](https://github.com/pulp/pulp_ansible/issues/1230), [#1245](https://github.com/pulp/pulp_ansible/issues/1245)

---

## 0.14.2 (2022-09-15) {: #0.14.2 }

#### Bugfixes

-   Update the jsonschema requirements to not conflict with ansible-lint. Currently ansible-lint requires at least 4.9, so match that.
    [#1202](https://github.com/pulp/pulp_ansible/issues/1202)

---

## 0.14.1 (2022-09-09) {: #0.14.1 }

#### Misc

-   [#1230](https://github.com/pulp/pulp_ansible/issues/1230)

---

## 0.14.0 (2022-06-30) {: #0.14.0 }

#### Features

-   Enable support for the pulpcore setting `REDIRECT_TO_OBJECT_STORAGE=False`.
    [#943](https://github.com/pulp/pulp_ansible/issues/943)

#### Bugfixes

-   Fixed 500 error when accessing Galaxy APIs when distribution is not pointing to a repository.
    [#909](https://github.com/pulp/pulp_ansible/issues/909)
-   Allow deleting collection versions when another version of the collection satisfies requirements.
    [#933](https://github.com/pulp/pulp_ansible/issues/933)
-   Fixed generation of the redirect url to the object storage
    [#956](https://github.com/pulp/pulp_ansible/issues/956)
-   Fixed improper type `KeyringEnum` being generated in client bindings.
    [#973](https://github.com/pulp/pulp_ansible/issues/973)

#### Misc

-   [#1035](https://github.com/pulp/pulp_ansible/issues/1035)

---

## 0.13.6 (2023-02-03) {: #0.13.6 }

#### Bugfixes

-   Pinned the dependency upper bound on setuptools to <66.2.0. Newer versions introduce stricter
    PEP-440 parsing.
    [#1340](https://github.com/pulp/pulp_ansible/issues/1340)

#### Improved Documentation

-   Fixed linebreak issues in remote workflow cli examples.
    [#1328](https://github.com/pulp/pulp_ansible/issues/1328)

---

## 0.13.5 (2022-11-16) {: #0.13.5 }

#### Bugfixes

-   Switched the attribute token on CollectionRemotes not to be exposed in the API.
    [#1221](https://github.com/pulp/pulp_ansible/issues/1221)

#### Misc

-   [#1218](https://github.com/pulp/pulp_ansible/issues/1218)

---

## 0.13.4 (2022-08-23) {: #0.13.4 }

No significant changes.

---

## 0.13.3 (2022-08-22) {: #0.13.3 }

No significant changes.

---

## 0.13.2 (2022-06-17) {: #0.13.2 }

No significant changes.

---

## 0.13.1 (2022-06-15) {: #0.13.1 }

#### Bugfixes

-   Allow deleting collection versions when another version of the collection satisfies requirements.
    [#933](https://github.com/pulp/pulp_ansible/issues/933)
-   Fixed improper type `KeyringEnum` being generated in client bindings.
    [#973](https://github.com/pulp/pulp_ansible/issues/973)

---

## 0.13.0 (2022-04-11) {: #0.13.0 }

#### Features

-   Galaxy API Refactor stage 1

    Move the existing collection views under /plugin/ansible/.
    Redirects the legacy v3 endpoints to their counterparts in /plugin/ansible/.
    Adds a new configuration option ANSIBLE_DEFAULT_DISTRIBUTION_PATH that allows users to configure a default distribution base path for the API.
    Adds a new configuration option ANSIBLE_URL_NAMESPACE that allows django URL namespace to be set on reverse so that urls can be configured to point correctly to the galaxy APIs when pulp ansible is deployed as part of automation hub.
    Adds the get v3/artifacts/path/file API endpoint from galaxy_ng.
    Enable RedirectContentGuard.
    [#728](https://github.com/pulp/pulp_ansible/issues/728)

-   Added upload endpoint for `/content/ansible/collection_signatures/`
    [#837](https://github.com/pulp/pulp_ansible/issues/837)

-   Made certs dir configurable
    [#851](https://github.com/pulp/pulp_ansible/issues/851)

-   Add api endpoints to delete collections and collection versions.
    [#879](https://github.com/pulp/pulp_ansible/issues/879)

#### Bugfixes

-   Fixed `manifest` and `files` fields not being set when uploading a collection.
    [#840](https://github.com/pulp/pulp_ansible/issues/840)
-   Signatures are now properly generated from a collection's MANIFEST.json file.
    [#841](https://github.com/pulp/pulp_ansible/issues/841)
-   Fixed collection signature filtering by `signed_collection` and `signing_service`.
    [#860](https://github.com/pulp/pulp_ansible/issues/860)
-   Fix a bug where when a collection version is removed from a repository, it's associated signatures
    and deprecated content remains in the repository.
    [#889](https://github.com/pulp/pulp_ansible/issues/889)

---

## 0.12.1 (2022-04-11) {: #0.12.1 }

#### Bugfixes

-   Fixed `manifest` and `files` fields not being set when uploading a collection.
    [#840](https://github.com/pulp/pulp_ansible/issues/840)

---

## 0.12.0 (2022-02-02) {: #0.12.0 }

#### Features

-   Added Collection Signatures to the Galaxy V3 API to allow for syncing of signatures during a collection sync.
    [#748](https://github.com/pulp/pulp_ansible/issues/748)
-   Added `CollectionVersionSignature` content model to store signatures for Collections.
    [#757](https://github.com/pulp/pulp_ansible/issues/757)
-   Added API to serve Collection Signatures at `/pulp/api/v3/content/ansible/collection_signatures/`.
    [#758](https://github.com/pulp/pulp_ansible/issues/758)
-   Enabled Collection Remote to sync content that was initially synced using Git Remote.
    [#778](https://github.com/pulp/pulp_ansible/issues/778)

#### Bugfixes

-   Fixed the migrations 0035 and 0036 that handle the transition of deprecations to being repository
    content and used to fail on uniquenes constraints.
    [#791](https://github.com/pulp/pulp_ansible/issues/791)
-   Use proxy auth credentials of a Remote when syncing content
    [#801](https://github.com/pulp/pulp_ansible/issues/801)
-   Adds workaround to handle collections that do not have a `requires_ansible` in the
    `meta/runtime.yml` data. This can happen in collections from `galaxy.ansible.com`.
    [#806](https://github.com/pulp/pulp_ansible/issues/806)

#### Misc

-   [#813](https://github.com/pulp/pulp_ansible/issues/813)

---

## 0.11.1 (2021-12-20) {: #0.11.1 }

#### Misc

-   [#774](https://github.com/pulp/pulp_ansible/issues/774)

---

## YANKED 0.11.0 (2021-12-15) {: #0.11.0 }

#### Features

-   Added ability to sync only metadata from a Git remote. This is a tech preview feature. The
    functionality may change in the future.
    [#744](https://github.com/pulp/pulp_ansible/issues/744)
-   Syncing now excludes collection versions found at `/excludes/` endpoint of remote.
    [#750](https://github.com/pulp/pulp_ansible/issues/750)
-   Added a Git Remote that is used to sync content from Git repositories. This is a tech preview
    feature. The functionality may change in the future.
    [#751](https://github.com/pulp/pulp_ansible/issues/751)
-   Added ability to sync collections using GitRemote. This is a tech preview feature. The
    functionality may change in the future.
    [#752](https://github.com/pulp/pulp_ansible/issues/752)
-   Use `shared_resources` in tasks where appropriate.
    [#753](https://github.com/pulp/pulp_ansible/issues/753)

#### Bugfixes

-   Case-insensitive search for the `owner__username` and role `name` fields in the pulp_ansible role view (same as on galaxy.ansible.com).
    [#747](https://github.com/pulp/pulp_ansible/issues/747)

---

## 0.10.5 (2023-02-03) {: #0.10.5 }

#### Bugfixes

-   Pinned the dependency upper bound on setuptools to <66.2.0. Newer versions introduce stricter
    PEP-440 parsing.
    [#1340](https://github.com/pulp/pulp_ansible/issues/1340)

#### Improved Documentation

-   Fixed linebreak issues in remote workflow cli examples.
    [#1328](https://github.com/pulp/pulp_ansible/issues/1328)

---

## 0.10.4 (2022-11-17) {: #0.10.4 }

#### Bugfixes

-   Switched the attribute token on CollectionRemotes not to be exposed in the API.
    [#1221](https://github.com/pulp/pulp_ansible/issues/1221)

---

## 0.10.3 (2022-06-07) {: #0.10.3 }

#### Bugfixes

-   Syncing now excludes collection versions found at `/excludes/` endpoint of remote.
    [#960](https://github.com/pulp/pulp_ansible/issues/960)

---

## 0.10.2 (2022-01-31) {: #0.10.2 }

#### Bugfixes

-   Fixed the migrations 0035 and 0036 that handle the transition of deprecations to being repository
    content and used to fail on uniquenes constraints.
    [#791](https://github.com/pulp/pulp_ansible/issues/791)
-   Use proxy auth credentials of a Remote when syncing content
    [#801](https://github.com/pulp/pulp_ansible/issues/801)
-   Adds workaround to handle collections that do not have a `requires_ansible` in the
    `meta/runtime.yml` data. This can happen in collections from `galaxy.ansible.com`.
    [#806](https://github.com/pulp/pulp_ansible/issues/806)

---

## 0.10.1 (2021-10-05) {: #0.10.1 }

#### Bugfixes

-   Added a better error message when trying to sync a missing collection using V3 endpoints.
    [#9404](https://pulp.plan.io/issues/9404)
-   Ensure deprecation status is in sync with the remote
    [#9442](https://pulp.plan.io/issues/9442)
-   Fixed optimized mirror syncs erroneously removing all content in the repository.
    [#9476](https://pulp.plan.io/issues/9476)
-   Changed the use of `dispatch` to match the signature from pulpcore>=3.15.
    [#9483](https://pulp.plan.io/issues/9483)

#### Misc

-   [#9368](https://pulp.plan.io/issues/9368)

---

## 0.10.0 (2021-08-31) {: #0.10.0 }

#### Features

-   Made deprecation exportable/importable
    [#8205](https://pulp.plan.io/issues/8205)

#### Bugfixes

-   Fixed bug where sync tasks would open a lot of DB connections.
    [#9260](https://pulp.plan.io/issues/9260)

#### Deprecations and Removals

-   Turned collection deprecation status into a content.

    !!! warning
        Current deprecation history will be lost, only accounting for
        the latest repository version.

    [#8205](https://pulp.plan.io/issues/8205)

-   Dropped support for Python 3.6 and 3.7. pulp_ansible now supports Python 3.8+.
    [#9034](https://pulp.plan.io/issues/9034)

#### Misc

-   [#9119](https://pulp.plan.io/issues/9119)

---

## 0.9.2 (2021-10-04) {: #0.9.2 }

#### Bugfixes

-   Fixed optimized mirror syncs erroneously removing all content in the repository.
    (backported from #9476)
    [#9480](https://pulp.plan.io/issues/9480)

---

## 0.9.1 (2021-08-25) {: #0.9.1 }

#### Bugfixes

-   Improved performance on reporting progress on parsing collection metadata
    [#9137](https://pulp.plan.io/issues/9137)
-   Ensure galaxy-importer is used when uploading collections
    [#9220](https://pulp.plan.io/issues/9220)

#### Misc

-   [#9250](https://pulp.plan.io/issues/9250)

---

## 0.9.0 (2021-07-21) {: #0.9.0 }

#### Bugfixes

-   Renaming bindings to be compatible with pulpcore >= 3.14
    [#8971](https://pulp.plan.io/issues/8971)

#### Misc

-   [#8882](https://pulp.plan.io/issues/8882)

---

## 0.8.1 (2021-07-21) {: #0.8.1 }

#### Bugfixes

-   Fixed an error message which indicated that the remote url was invalid when in fact the requirements
    source url was invalid.
    [#8957](https://pulp.plan.io/issues/8957)
-   Use proxy auth credentials of a Remote when syncing content.
    [#9075](https://pulp.plan.io/issues/9075)

#### Misc

-   [#9006](https://pulp.plan.io/issues/9006)

---

## 0.8.0 (2021-06-01) {: #0.8.0 }

#### Features

-   Pulp Ansible can now sync collection dependencies by setting the `sync_dependencies` option for `CollectionRemote` objects.
    (By default set to true)
    [#7751](https://pulp.plan.io/issues/7751)
-   Enabled pulp_label support for AnsibleDistributions
    [#8441](https://pulp.plan.io/issues/8441)
-   Provide backend storage url to galaxy-importer on collection import.
    [#8486](https://pulp.plan.io/issues/8486)

#### Bugfixes

-   /collection_versions/all/ endpoint is now streamed to alleviate timeout issues
    [#8439](https://pulp.plan.io/issues/8439)
-   V3 sync now properly waits for async task completion
    [#8442](https://pulp.plan.io/issues/8442)
-   Remove scheme from apache snippet
    [#8572](https://pulp.plan.io/issues/8572)
-   Fix collections endpoint for collections named "api"
    [#8587](https://pulp.plan.io/issues/8587)
-   Fix requirements.yml parser for pinned collection version
    [#8627](https://pulp.plan.io/issues/8627)
-   Fixed dependency syncing slowing down from excessive task creation
    [#8639](https://pulp.plan.io/issues/8639)
-   Updated api lengths for collection version fields to match db model lengths.
    [#8649](https://pulp.plan.io/issues/8649)
-   Optimized unpaginated collection_versions endpoint
    [#8746](https://pulp.plan.io/issues/8746)

#### Improved Documentation

-   Fixed broken link on client bindings page
    [#8298](https://pulp.plan.io/issues/8298)

#### Misc

-   [#8589](https://pulp.plan.io/issues/8589)

---

## 0.7.6 (2022-06-07) {: #0.7.6 }

#### Bugfixes

-   Syncing now excludes collection versions found at `/excludes/` endpoint of remote.
    [#959](https://github.com/pulp/pulp_ansible/issues/959)
-   Fixed optimized mirror syncs erroneously removing all content in the repository.
    [#974](https://github.com/pulp/pulp_ansible/issues/974)

---

## 0.7.5 (2022-01-31) {: #0.7.5 }

#### Bugfixes

-   Use proxy auth credentials of a Remote when syncing content
    [#801](https://github.com/pulp/pulp_ansible/issues/801)
-   Adds workaround to handle collections that do not have a `requires_ansible` in the
    `meta/runtime.yml` data. This can happen in collections from `galaxy.ansible.com`.
    [#806](https://github.com/pulp/pulp_ansible/issues/806)

---

## 0.7.4 (2021-11-12) {: #0.7.4 }

#### Bugfixes

-   /collection_versions/all/ endpoint is now streamed to alleviate timeout issues
    Optimized unpaginated collection_versions endpoint
    (backported from #8439 and #8746) rochacbruno
    [#8923](https://pulp.plan.io/issues/8923)
-   Use proxy auth credentials of a Remote when syncing content. Warning: This is not a proper fix.
    The actual fix is shipped with 0.7.5.
    [#9391](https://pulp.plan.io/issues/9391)

#### Misc

-   [#8857](https://pulp.plan.io/issues/8857)

---

## 0.7.3 (2021-04-29) {: #0.7.3 }

#### Bugfixes

-   Fix requirements.yml parser for pinned collection version
    [#8647](https://pulp.plan.io/issues/8647)
-   V3 sync now properly waits for async task completion
    [#8664](https://pulp.plan.io/issues/8664)
-   Remove scheme from apache snippet
    [#8665](https://pulp.plan.io/issues/8665)
-   Fix collections endpoint for collections named "api"
    [#8666](https://pulp.plan.io/issues/8666)
-   Updated api lengths for collection version fields to match db model lengths.
    [#8667](https://pulp.plan.io/issues/8667)

---

## 0.7.2 (2021-04-09) {: #0.7.2 }

No significant changes.

---

## 0.7.1 (2021-03-04) {: #0.7.1 }

#### Bugfixes

-   Removing `manifest` and `files` from metadata endpoints.
    [#8264](https://pulp.plan.io/issues/8264)
-   Fix V3 collection list endpoint when repository is empty
    [#8276](https://pulp.plan.io/issues/8276)
-   Use DRF token when no `auth_url` is provided
    [#8290](https://pulp.plan.io/issues/8290)
-   Fixed bug where rate limit wasn't being honored.
    [#8300](https://pulp.plan.io/issues/8300)

---

## 0.7.0 (2021-02-11) {: #0.7.0 }

#### Features

-   Ansible export/import is now available as a tech preview feature
    [#6738](https://pulp.plan.io/issues/6738)
-   Expose MANIFEST.json and FILES.json at CollectionVersion endpoint
    [#7572](https://pulp.plan.io/issues/7572)
-   Introduce a new `v3/` endpoint returning publication time
    [#7939](https://pulp.plan.io/issues/7939)
-   Introduces a new `v3/collections/all/` endpoint returning all collections unpaginated.
    [#7940](https://pulp.plan.io/issues/7940)
-   Introduces a new `v3/collection_versions/all/` endpoint returning all collections versions
    unpaginated.
    [#7941](https://pulp.plan.io/issues/7941)
-   Improve sync performance with no-op when possible. To disable the no-op optimization use the
    `optimize=False` option on the `sync` call.
    [#7942](https://pulp.plan.io/issues/7942)
-   Adds the `requires_ansible` attribute to the Galaxy V3 CollectionVersion APIs.
    This documents the version of Ansible required to use the collection.
    [#7949](https://pulp.plan.io/issues/7949)
-   Field `updated_at` from Galaxy v3 Collections endpoint using latest instead of highest version
    [#8012](https://pulp.plan.io/issues/8012)
-   Efficient sync with unpaginated metadata endpoints if they are available.
    [#8177](https://pulp.plan.io/issues/8177)

#### Bugfixes

-   Make collection namespace max_length consistent in models
    [#8078](https://pulp.plan.io/issues/8078)

#### Improved Documentation

-   Move official docs site to <https://docs.pulpproject.org/pulp_ansible/>.
    [#7926](https://pulp.plan.io/issues/7926)
-   Updated Roles and Collections workflows to use Pulp-CLI commands
    [#8076](https://pulp.plan.io/issues/8076)

#### Misc

-   [#8216](https://pulp.plan.io/issues/8216)

---

## 0.6.2 (2021-03-03) {: #0.6.2 }

#### Bugfixes

-   Use DRF token when no `auth_url` is provided
    [#8290](https://pulp.plan.io/issues/8290)

---

## 0.6.1 (2021-01-15) {: #0.6.1 }

#### Bugfixes

-   Allow updating `auth_url` on CollectionRemote when `token` is already set
    [#7957](https://pulp.plan.io/issues/7957)
-   Fixed create_task calls for Python 3.6 in collections tasks
    [#8098](https://pulp.plan.io/issues/8098)

---

## 0.6.0 (2020-12-01) {: #0.6.0 }

#### Features

-   Enable filter by name/namespace on Collections V3 endpoint
    [#7873](https://pulp.plan.io/issues/7873)

#### Bugfixes

-   Allows a requirements.yml collection version specification to be respected during sync.
    [#7739](https://pulp.plan.io/issues/7739)
-   Allow requirements.yml with different sources to sync correctly.
    [#7741](https://pulp.plan.io/issues/7741)
-   Increased collection tag field length from 32 to 64, which allows sync to work for longer tag names
    used on galaxy.ansible.com.
    [#7827](https://pulp.plan.io/issues/7827)

#### Misc

-   [#7777](https://pulp.plan.io/issues/7777)

---

## 0.5.11 (2022-01-31) {: #0.5.11 }

#### Bugfixes

-   Use proxy auth credentials of a Remote when syncing content
    [#801](https://github.com/pulp/pulp_ansible/issues/801)

---

## 0.5.10 (2021-09-13) {: #0.5.10 }

#### Bugfixes

-   Use proxy auth credentials of a Remote when syncing content.
    [#9390](https://pulp.plan.io/issues/9390)

---

## 0.5.9 (2021-04-29) {: #0.5.9 }

#### Bugfixes

-   Remove scheme from apache snippet
    [#8661](https://pulp.plan.io/issues/8661)
-   Fix collections endpoint for collections named "api"
    [#8662](https://pulp.plan.io/issues/8662)
-   Updated api lengths for collection version fields to match db model lengths.
    [#8663](https://pulp.plan.io/issues/8663)

---

## 0.5.8 (2021-03-08) {: #0.5.8 }

#### Bugfixes

-   Allow updating `auth_url` on CollectionRemote when `token` is already set
    [#8362](https://pulp.plan.io/issues/8362)

---

## 0.5.7 (2021-03-03) {: #0.5.7 }

#### Bugfixes

-   Use DRF token when no `auth_url` is provided
    [#8290](https://pulp.plan.io/issues/8290)

---

## 0.5.6 (2021-01-12) {: #0.5.6 }

#### Bugfixes

-   Fixed v3 schema pagination to match OpenAPI standard
    [#8037](https://pulp.plan.io/issues/8037)
-   Fix collection version comparison on re-syncs
    [#8039](https://pulp.plan.io/issues/8039)
-   Enable proxy on token refresh requests
    [#8051](https://pulp.plan.io/issues/8051)

---

## 0.5.5 (2020-12-11) {: #0.5.5 }

#### Bugfixes

-   Field `updated_at` from Galaxy v3 Collections endpoint using highest version
    [#7990](https://pulp.plan.io/issues/7990)

---

## 0.5.4 (2020-12-04) {: #0.5.4 }

#### Bugfixes

-   Increase interval between requests when token is required
    [#7929](https://pulp.plan.io/issues/7929)

---

## 0.5.3 (2020-12-04) {: #0.5.3 }

#### Bugfixes

-   Avoid rate limiting by slowing down sync when token is required
    [#7917](https://pulp.plan.io/issues/7917)

---

## 0.5.2 (2020-11-19) {: #0.5.2 }

#### Bugfixes

-   Improve MANIFEST.json handling and provide better error message
    [#5745](https://pulp.plan.io/issues/5745)
-   Ensure that when creating a `CollectionRemote` you can use `token` without specifying `auth_url`
    [#7821](https://pulp.plan.io/issues/7821)
-   Fix version comparisons during sync and upload when comparing the same version with different build
    numbers.
    [#7826](https://pulp.plan.io/issues/7826)
-   Stop making requests to docs-blob endpoint on Galaxy v2
    [#7830](https://pulp.plan.io/issues/7830)
-   Avoid to download docs-blob when content is already saved
    [#7831](https://pulp.plan.io/issues/7831)
-   Ensure deprecation status is synced even when no content changes
    [#7834](https://pulp.plan.io/issues/7834)
-   Fix deprecation status update for pulp-ansible-client
    [#7871](https://pulp.plan.io/issues/7871)
-   Makes `url` optional when patching a collection remote
    [#7872](https://pulp.plan.io/issues/7872)

---

## 0.5.1 (2020-11-09) {: #0.5.1 }

#### Bugfixes

-   Token refresh happens when needed, not on every call.
    [#7643](https://pulp.plan.io/issues/7643)
-   Field `updated_at` from Galaxy v3 Collections endpoint using latest instead of highest version
    [#7775](https://pulp.plan.io/issues/7775)
-   Allow CollectionUploadViewSet subclass to set own serializer
    [#7788](https://pulp.plan.io/issues/7788)
-   Ensure that when creating a `CollectionRemote` with either a `token` or `auth_url` that you
    use both together.
    [#7802](https://pulp.plan.io/issues/7802)

---

## 0.5.0 (2020-10-29) {: #0.5.0 }

#### Features

-   Adds a new `/pulp/api/v3/ansible/copy/` endpoint allowing content to be copied from one
    `AnsibleRepository` version to a destination `AnsibleRepository`.
    [#7621](https://pulp.plan.io/issues/7621)

#### Bugfixes

-   Sync collection deprecation status
    [#7504](https://pulp.plan.io/issues/7504)
-   Supporting url formats that conform to ansible-galaxy cli (e.g. "<https://galaxy.ansible.com>" and
    "<https://galaxy.ansible.com/api>").
    [#7686](https://pulp.plan.io/issues/7686)
-   Fixed bug where only 10 collections were being synced in some cases
    [#7740](https://pulp.plan.io/issues/7740)
-   Fixed syncing with a default remote.
    [#7742](https://pulp.plan.io/issues/7742)
-   Increase the version size for `CollectionVersions`.
    [#7745](https://pulp.plan.io/issues/7745)
-   Fixed bug where we didn't properly handle trailing slashes.
    [#7767](https://pulp.plan.io/issues/7767)

#### Deprecations and Removals

-   Remove 'certification' flag from CollectionVersion
    [#6715](https://pulp.plan.io/issues/6715)
-   Derive ANSIBLE_CONTENT_HOSTNAME from CONTENT_ORIGIN
    [#7368](https://pulp.plan.io/issues/7368)
-   Removing deprecated field from Collection
    [#7504](https://pulp.plan.io/issues/7504)
-   Url formats must conform to ansible-galaxy cli format (e.g. "<https://galaxy.ansible.com>" and
    "<https://galaxy.ansible.com/api>"). This means we no longer support urls such as
    "<https://galaxy.ansible.com/api/v2/collections>" or
    "<https://galaxy.ansible.com/api/v2/collections/amazon/aws>".
    [#7686](https://pulp.plan.io/issues/7686)
-   Galaxy URLs now require trailing slashes per the ansible-galaxy docs. Made an exception for
    "<https://galaxy.ansible.com>" since the ansible-galaxy CLI code does as well.
    [#7767](https://pulp.plan.io/issues/7767)

---

## 0.4.3 (2020-11-04) {: #0.4.3 }

#### Features

-   Allow CollectionUploadViewSet subclass to set own serializer
    [#7788](https://pulp.plan.io/issues/7788)

---

## 0.4.2 (2020-10-09) {: #0.4.2 }

#### Bugfixes

-   Update Collection serializer to match Galaxy v2
    [#7647](https://pulp.plan.io/issues/7647)
-   Fix galaxy collection endpoint results for empty repos
    [#7669](https://pulp.plan.io/issues/7669)

---

## 0.4.1 (2020-09-30) {: #0.4.1 }

#### Bugfixes

-   Fixing docs-blob file parser
    [#7551](https://pulp.plan.io/issues/7551)
-   Sync CollectionVersion metadata
    [#7632](https://pulp.plan.io/issues/7632)

---

## 0.4.0 (2020-09-23) {: #0.4.0 }

#### Bugfixes

-   List highest versions per repository
    [#7428](https://pulp.plan.io/issues/7428)
-   Fix skipped collections at requirements.yml
    [#7512](https://pulp.plan.io/issues/7512)

---

## 0.3.0 (2020-09-09) {: #0.3.0 }

#### Features

-   Add endpoint to show docs_blob for a CollectionVersion
    [#7397](https://pulp.plan.io/issues/7397)
-   Allow the requirements file field on remotes to be of longer length.
    [#7434](https://pulp.plan.io/issues/7434)
-   Sync docs_blob information for collection versions
    [#7439](https://pulp.plan.io/issues/7439)

#### Bugfixes

-   Replace URLField with CharField
    [#7353](https://pulp.plan.io/issues/7353)
-   Pagination query params according to API versions.
    v1 and v2 - page and page_size
    v3 or above - offset and limit
    [#7396](https://pulp.plan.io/issues/7396)
-   Build collections URL according to requirements.yml
    [#7412](https://pulp.plan.io/issues/7412)

#### Deprecations and Removals

-   Changed V3 pagination to match Galaxy V3 API pagination
    [#7435](https://pulp.plan.io/issues/7435)

#### Misc

-   [#7453](https://pulp.plan.io/issues/7453)

---

## 0.2.0 (2020-08-17) {: #0.2.0 }

#### Features

-   Allow a Remote to be associated with a Repository and automatically use it when syncing the
    Repository.
    [#7194](https://pulp.plan.io/issues/7194)

#### Deprecations and Removals

-   Moved the role remote path from `/pulp/api/v3/remotes/ansible/ansible/` to
    `/pulp/api/v3/remotes/ansible/role/` to be consistent with
    `/pulp/api/v3/remotes/ansible/collection/`.
    [#7305](https://pulp.plan.io/issues/7305)

#### Misc

-   [#6718](https://pulp.plan.io/issues/6718)

---

## 0.2.0b15 (2020-07-14)

#### Features

-   Enable token authentication for syncing Collections.
    Added auth_url and token [fields](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html#configuring-the-ansible-galaxy-client) to CollectionRemote
    [#6540](https://pulp.plan.io/issues/6540)

---

## 0.2.0b14 (2020-06-19)

#### Bugfixes

-   Make default page size equals to 100
    [#5494](https://pulp.plan.io/issues/5494)
-   Including requirements.txt on MANIFEST.in
    [#6889](https://pulp.plan.io/issues/6889)

#### Misc

-   [#6772](https://pulp.plan.io/issues/6772)

---

## 0.2.0b13 (2020-05-28)

#### Features

-   Increased max length for documentation, homepage, issues, repository in CollectionVersion
    [#6648](https://pulp.plan.io/issues/6648)

#### Bugfixes

-   Galaxy V3 download_url now uses fully qualified URL
    [#6510](https://pulp.plan.io/issues/6510)
-   Include readable error messages on user facing logger
    [#6657](https://pulp.plan.io/issues/6657)
-   Fix filename generation for ansible collection artifacts.
    [#6855](https://pulp.plan.io/issues/6855)

#### Improved Documentation

-   Updated the required roles names
    [#6760](https://pulp.plan.io/issues/6760)

#### Misc

-   [#6673](https://pulp.plan.io/issues/6673), [#6848](https://pulp.plan.io/issues/6848), [#6850](https://pulp.plan.io/issues/6850)

---

## 0.2.0b12 (2020-04-30)

#### Improved Documentation

-   Documented bindings installation on dev environment
    [#6390](https://pulp.plan.io/issues/6390)

#### Misc

-   [#6391](https://pulp.plan.io/issues/6391)

---

## 0.2.0b11 (2020-03-13)

#### Features

-   Add support for syncing collections from Automation Hub's v3 api.
    [#6132](https://pulp.plan.io/issues/6132)

#### Bugfixes

-   Including file type extension when uploading collections.
    This comes with a data migration that will fix incorrect fields for already uploaded collections.
    [#6223](https://pulp.plan.io/issues/6223)

#### Improved Documentation

-   Added docs on how to use the new scale testing tools.
    [#6272](https://pulp.plan.io/issues/6272)

#### Misc

-   [#6155](https://pulp.plan.io/issues/6155), [#6223](https://pulp.plan.io/issues/6223), [#6272](https://pulp.plan.io/issues/6272), [#6300](https://pulp.plan.io/issues/6300)

---

## 0.2.0b10 (2020-02-29)

#### Bugfixes

-   Includes webserver snippets in the packaged version also.
    [#6248](https://pulp.plan.io/issues/6248)

#### Misc

-   [#6250](https://pulp.plan.io/issues/6250)

---

## 0.2.0b9 (2020-02-28)

#### Bugfixes

-   Fix 404 error with ansible-galaxy 2.10.0 while staying compatible with 2.9.z CLI clients also.
    [#6239](https://pulp.plan.io/issues/6239)

#### Misc

-   [#6188](https://pulp.plan.io/issues/6188)

---

## 0.2.0b8 (2020-02-02)

#### Bugfixes

-   Fixed `ansible-galaxy publish` command which was failing with a 400 error.
    [#5905](https://pulp.plan.io/issues/5905)
-   Fixes `ansible-galaxy role install` when installing from Pulp.
    [#5929](https://pulp.plan.io/issues/5929)

#### Improved Documentation

-   Heavy overhaul of workflow docs to be two long pages that are focused on the `ansible-galaxy` cli.
    [#4889](https://pulp.plan.io/issues/4889)

#### Misc

-   [#5867](https://pulp.plan.io/issues/5867), [#5929](https://pulp.plan.io/issues/5929), [#5930](https://pulp.plan.io/issues/5930), [#5931](https://pulp.plan.io/issues/5931)

---

## 0.2.0b7 (2019-12-16)

#### Features

-   Add "modify" endpoint as `/pulp/api/v3/repositories/ansible/ansible/<uuid>/modify/`.
    [#5783](https://pulp.plan.io/issues/5783)

#### Improved Documentation

-   Adds copyright notice to source.
    [#4592](https://pulp.plan.io/issues/4592)

#### Misc

-   [#5693](https://pulp.plan.io/issues/5693), [#5701](https://pulp.plan.io/issues/5701), [#5757](https://pulp.plan.io/issues/5757)

---

## 0.2.0b6 (2019-11-20)

#### Features

-   Add Ansible Collection endpoint.
    [#5520](https://pulp.plan.io/issues/5520)
-   Added since filter for CollectionImport messsages.
    [#5522](https://pulp.plan.io/issues/5522)
-   Add a tags filter by which to filter collection versions.
    [#5571](https://pulp.plan.io/issues/5571)
-   Allow users to update deprecated for collections endpoint.
    [#5577](https://pulp.plan.io/issues/5577)
-   Add the ability to set a certification status for a collection version.
    [#5579](https://pulp.plan.io/issues/5579)
-   Add sorting parameters to the collection versions endpoint.
    [#5621](https://pulp.plan.io/issues/5621)
-   Expose the deprecated field on collection versions and added a deprecated filter.
    [#5645](https://pulp.plan.io/issues/5645)
-   Added filters to v3 collection version endpoint
    [#5670](https://pulp.plan.io/issues/5670)

#### Bugfixes

-   Reverting back to the older upload serializers.
    [#5555](https://pulp.plan.io/issues/5555)
-   Fix bug where CollectionImport was not being created in viewset causing 404s for galaxy.
    [#5569](https://pulp.plan.io/issues/5569)
-   Fixed an old call to _id in a collection task.
    [#5572](https://pulp.plan.io/issues/5572)
-   Fix 500 error for /pulp/api/v3/ page and drf_yasg error on api docs.
    [#5748](https://pulp.plan.io/issues/5748)

#### Deprecations and Removals

-   Change _id, _created, _last_updated, _href to pulp_id, pulp_created, pulp_last_updated, pulp_href
    [#5457](https://pulp.plan.io/issues/5457)

-   Remove "_" from _versions_href, _latest_version_href
    [#5548](https://pulp.plan.io/issues/5548)

-   Removing base field: _type .
    [#5550](https://pulp.plan.io/issues/5550)

-   Change is_certified to certification enum on CollectionVersion.
    [#5579](https://pulp.plan.io/issues/5579)

-   Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

    Creating / listing / editing / deleting Ansible repositories is now performed on /pulp/api/v3/ansible/ansible/ instead of /pulp/api/v3/repositories/. Only Ansible content can be present in a Ansible repository, and only a Ansible repository can hold Ansible content.
    [#5625](https://pulp.plan.io/issues/5625)

-   Removing unnecessary DELETE action for set_certified method.
    [#5711](https://pulp.plan.io/issues/5711)

#### Misc

-   [#4554](https://pulp.plan.io/issues/4554), [#5580](https://pulp.plan.io/issues/5580), [#5629](https://pulp.plan.io/issues/5629)

---

## 0.2.0b5 (2019-10-01)

#### Misc

-   [#5462](https://pulp.plan.io/issues/5462), [#5468](https://pulp.plan.io/issues/5468)

---

## 0.2.0b3 (2019-09-18)

#### Features

-   Setting code on ProgressBar.
    [#5184](https://pulp.plan.io/issues/5184)
-   Add galaxy-importer into import_collection to parse and validate collection.
    [#5239](https://pulp.plan.io/issues/5239)
-   Add Collection upload endpoint to Galaxy V3 API.
    [#5243](https://pulp.plan.io/issues/5243)
-   Introduces the GALAXY_API_ROOT setting that lets you re-root the Galaxy API.
    [#5244](https://pulp.plan.io/issues/5244)
-   Add [requirements.yaml](https://docs.ansible.com/ansible/devel/dev_guide/collections_tech_preview.html#install-multiple-collections-with-a-requirements-file) specification support to collection sync.
    [#5250](https://pulp.plan.io/issues/5250)
-   Adding is_highest filter for Collection Version.
    [#5278](https://pulp.plan.io/issues/5278)
-   Add certified collections status support.
    [#5287](https://pulp.plan.io/issues/5287)
-   Support pulp-to-pulp syncing of collections by expanding galaxy API views/serializers
    [#5288](https://pulp.plan.io/issues/5288)
-   Add model for tracking collection import status.
    [#5300](https://pulp.plan.io/issues/5300)
-   Add collection imports endpoints.
    [#5301](https://pulp.plan.io/issues/5301)
-   Uploaded collections through the Galaxy V2 and V3 APIs now auto-create a RepositoryVersion for the
    Repository associated with the AnsibleDistribution.
    [#5334](https://pulp.plan.io/issues/5334)
-   Added support for ansible-galaxy collections command and removed mazer.
    [#5335](https://pulp.plan.io/issues/5335)
-   CollectionImport object is created on collection upload.
    [#5358](https://pulp.plan.io/issues/5358)
-   Adds id field to collection version items returned by API.
    [#5365](https://pulp.plan.io/issues/5365)
-   The Galaxy V3 artifacts/collections/ API now logs correctly during the import process.
    [#5366](https://pulp.plan.io/issues/5366)
-   Write galaxy-importer result of contents and docs_blob into CollectionVersion model
    [#5368](https://pulp.plan.io/issues/5368)
-   The Galaxy v3 API validates the tarball's binary data before import using the optional arguments
    expected_namespace, expected_name, and expected_version.
    [#5422](https://pulp.plan.io/issues/5422)
-   Settings `ANSIBLE_API_HOSTNAME` and `ANSIBLE_CONTENT_HOSTNAME` now have defaults that use your
    FQDN, which works with [the installer](https://github.com/pulp/ansible-pulp) defaults.
    [#5466](https://pulp.plan.io/issues/5466)

#### Bugfixes

-   Treating how JSONFields will be handled by OpenAPI.
    [#5299](https://pulp.plan.io/issues/5299)
-   Galaxy API v3 collection upload returns valid imports URL.
    [#5357](https://pulp.plan.io/issues/5357)
-   Fix CollectionVersion view imcompatibilty with ansible-galaxy.
    Fixes ansible issue <https://github.com/ansible/ansible/issues/62076>
    [#5459](https://pulp.plan.io/issues/5459)

#### Improved Documentation

-   Added documentation on all settings.
    [#5244](https://pulp.plan.io/issues/5244)

#### Deprecations and Removals

-   Removing latest filter Collection Version.
    [#5227](https://pulp.plan.io/issues/5227)
-   Removed support for mazer cli.
    [#5335](https://pulp.plan.io/issues/5335)
-   Renamed _artifact on content creation to artifact.
    [#5428](https://pulp.plan.io/issues/5428)

#### Misc

-   [#4681](https://pulp.plan.io/issues/4681), [#5236](https://pulp.plan.io/issues/5236), [#5262](https://pulp.plan.io/issues/5262), [#5332](https://pulp.plan.io/issues/5332), [#5333](https://pulp.plan.io/issues/5333)

---

## 0.2.0b2 (2019-08-12)

#### Features

-   Fulltext Collection search is available with the `q` filter argument. A migration creates
    databases indexes to speed up the search.
    [#5075](https://pulp.plan.io/issues/5075)
-   Sync all collections (a full mirror) from Galaxy.
    [#5165](https://pulp.plan.io/issues/5165)
-   Mirror ansible collection
    [#5167](https://pulp.plan.io/issues/5167)
-   Added new fields to CollectionVersion and extended the CollectionVersion upload and sync to populate
    the data correctly. The serializer displays the new fields. The 'tags' field in serializer also has
    its own viewset for filtering on Tag objects system-wide.
    [#5198](https://pulp.plan.io/issues/5198)
-   Custom error handling and pagination for Galaxy API v3 is available.
    [#5224](https://pulp.plan.io/issues/5224)
-   Implements Galaxy API v3 collections and collection versions endpoints
    [#5225](https://pulp.plan.io/issues/5225)

#### Bugfixes

-   Validating collection remote URL
    [#4996](https://pulp.plan.io/issues/4996)
-   Validates artifact creation when uploading a collection
    [#5209](https://pulp.plan.io/issues/5209)
-   Fixes exception when generating initial full text search index on more than one collection.
    [#5226](https://pulp.plan.io/issues/5226)

#### Deprecations and Removals

-   Removing whitelist field from CollectionRemote.
    [#5165](https://pulp.plan.io/issues/5165)

#### Misc

-   [#4970](https://pulp.plan.io/issues/4970), [#5106](https://pulp.plan.io/issues/5106), [#5223](https://pulp.plan.io/issues/5223)

---

## 0.2.0b1 (2019-07-12)

#### Features

-   Adds Artifact sha details to the Collection list and detail APIs.
    [#4827](https://pulp.plan.io/issues/4827)
-   Collection sync now provides basic progress reporting.
    [#5023](https://pulp.plan.io/issues/5023)
-   A new Collection uploader has been added to the pulp_ansible API at
    `/pulp/api/v3/ansible/collections/`.
    [#5050](https://pulp.plan.io/issues/5050)
-   Collection filtering now supports the 'latest' boolean. When True, only the most recent version of
    each `namespace` and `name` combination is included in filter results.
    [#5076](https://pulp.plan.io/issues/5076)

#### Bugfixes

-   Collection sync now creates a new RepositoryVersion even if no new Collection content was added.
    [#4920](https://pulp.plan.io/issues/4920)
-   Content present in a second sync now associates correctly with the newly created Repository Version.
    [#4997](https://pulp.plan.io/issues/4997)
-   Collection sync no longer logs errors about a missing directory named 'ansible_collections'
    [#4999](https://pulp.plan.io/issues/4999)

#### Improved Documentation

-   Switch to using [towncrier](https://github.com/hawkowl/towncrier) for better release notes.
    [#4875](https://pulp.plan.io/issues/4875)
-   Add documentation on Collection upload workflows.
    [#4939](https://pulp.plan.io/issues/4939)
-   Update the REST API docs to the latest by updating the committed openAPI schema.
    [#5001](https://pulp.plan.io/issues/5001)
