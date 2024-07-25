# Copy Workflows

If you want to copy Ansible Collections or Roles from one repository into another repository, you
have two options for doing so.



## Basic Repository Modification API

Like all Pulp repositories, you can use the \$\{repo_href}/modify/ endpoint to:

- add or remove individual Collections or Roles from a repository by HREF
- roll back the content present in a repository to that of a previous version using 'base_version'
- clone a repository version using '"base_version". This operation will create a new repository
  version in the current repository which is a copy of the one specified as the "base_version",
  regardless of what content was previously present in the repository. This can be combined with
  adding and removing content units in the same call.

For example:

```
http POST localhost/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/modify/ \
    add_content_units:="['/pulp/api/v3/content/ansible/collections/d2bab58c-50f2-4f1d-9cf0-8ceb1680f31b/']"
```

% copy-workflow:

## Advanced Copy Workflow

Ansible Collections store their `deprecated` status data at the Repository Version level, and the
"modify" workflow above does not properly preserve `deprecated` because the source of the content
is not known. For this reason a `copy` endpoint is available at `/pulp/api/v3/ansible/copy/`
which is similar to modify except the source of content, e.g. Collections, is declared which
allows the `deprecated` status to follow the content.

For example say you have two `AnsibleRepository` Repositories two `AnsibleDistribution`
Distributions exposing their content. One contains Collections with `deprecate=True` and the other
has no Collections in it.

Viewing the Repository with content you can see:

```
http GET http://example.com/pulp_ansible/galaxy/my_content/api/v3/collections/

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Vary: Accept

{
    "meta": {
        "count": 1
    },
    "links": {
        "first": "/pulp_ansible/galaxy/my_content/api/v3/collections/?limit=10&offset=0",
        "previous": null,
        "next": null,
        "last": "/pulp_ansible/galaxy/my_content/api/v3/collections/?limit=10&offset=0"
    },
    "data": [
        {
            "href": "/pulp_ansible/galaxy/my_content/api/v3/collections/testing/k8s_demo_collection/",
            "namespace": "testing",
            "name": "k8s_demo_collection",
            "deprecated": true,
            "versions_url": "/pulp_ansible/galaxy/my_content/api/v3/collections/testing/k8s_demo_collection/versions/",
            "highest_version": {
                "href": "/pulp_ansible/galaxy/my_content/api/v3/collections/testing/k8s_demo_collection/versions/0.0.3/",
                "version": "0.0.3"
            },
            "created_at": "2020-10-28T19:22:24.577606Z",
            "updated_at": "2020-10-28T19:22:24.577606Z"
        }
    ]
}
```

Then viewing the empty repository you can see:

```
http GET http://example.com/pulp_ansible/galaxy/dest_repo/api/v3/collections/

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Vary: Accept

{
    "meta": {
        "count": 0
    },
    "links": {
        "first": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/?limit=10&offset=0",
        "previous": null,
        "next": null,
        "last": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/?limit=10&offset=0"
    },
    "data": []
}
```

In this situation if you use the `modify` call since it doesn't know which Repository Version to
take the `deprecated` data from it isn't preserved For example if you run:

```
http POST http://example.com/pulp/api/v3/repositories/ansible/ansible/05813fa6-cf0b-435b-b54b-5a30fc370848/modify/ \
    add_content_units:="['/pulp/api/v3/content/ansible/collections/d2bab58c-50f2-4f1d-9cf0-8ceb1680f31b/']"
```

And you list the dest_repo via the Galaxy V3 API (that the CLI uses) you would see
`deprecated=False`.

However you could instead use the `copy` API as follows:

```bash
POST /pulp/api/v3/ansible/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$CONTENT_HREF1]}
]
```

Then if you list the contents on the destination repository, you would see the `deprecated=True`
was preserved:

```
http GET http://example.com/pulp_ansible/galaxy/dest_repo/api/v3/collections/

HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Vary: Accept

{
    "meta": {
        "count": 1
    },
    "links": {
        "first": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/?limit=10&offset=0",
        "previous": null,
        "next": null,
        "last": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/?limit=10&offset=0"
    },
    "data": [
        {
            "href": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/testing/k8s_demo_collection/",
            "namespace": "testing",
            "name": "k8s_demo_collection",
            "deprecated": true,
            "versions_url": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/testing/k8s_demo_collection/versions/",
            "highest_version": {
                "href": "/pulp_ansible/galaxy/dest_repo/api/v3/collections/testing/k8s_demo_collection/versions/0.0.3/",
                "version": "0.0.3"
            },
            "created_at": "2020-10-28T19:22:24.577606Z",
            "updated_at": "2020-10-28T19:22:24.577606Z"
        }
    ]
}
```

## Copy All Content

When calling `copy` you can omit the `content` argument and `copy` will copy all content from
the `source_repo_version` to a new Repository Version created on the `dest_repo`. That would be
similar to:

```bash
POST /pulp/api/v3/ansible/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF"}
]
```

## Specifying a Destination Base Version

In some situations, you may want the content being copied to be applied not to the latest version
of the `dest_repo`, and in that case, you can additionally specify the `dest_base_version` and
that would be used instead of the latest RepositoryVersion of `dest_repo`:

```bash
POST /pulp/api/v3/ansible/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "dest_base_version": "$DEST_BASE_VERSION", "content": [$CONTENT_HREF1, $CONTENT_HREF2]}
]
```

## Multi-Repo Copy

You can specify a more complicated `config` option which can express multiple copy operations in
one call. Each entry is the dictionary of `source_repo_version`, `dest_repo`, and optional
`content`, in a list form.

```bash
POST /pulp/api/v3/ansible/copy/
config:=[
    {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$CONTENT_HREF1, $CONTENT_HREF2]},
    {"source_repo_version": "$SRC_REPO_VERS_HREF2", "dest_repo": "$DEST_REPO_HREF2", "content": []},
]
```
