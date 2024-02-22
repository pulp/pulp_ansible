# Role Workflows

Pulp organizes role content into repositories, and you associate the `ansible-galaxy` client with
one or more repositories. From a high level you can:

1. `Create a repo <create-a-roles-repository>`
2. `Create a distribution <create-distribution-for-repo>` expose that repository at a URL
3. `Sync content from galaxy.ansible.com <create-role-remote>`
4. `Install content from the repo with ansible-galaxy <ansible-galaxy-roles-cli>`


## Create a Repository

Create a repository and name it the `foo` repository.

```bash
# Start by creating a new repository named foo
pulp ansible repository create --name "foo"
```

Repository create output:

```json
{
  "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/",
  "pulp_created": "2021-01-26T22:48:11.479496Z",
  "versions_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/",
  "latest_version_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/0/",
  "name": "foo",
  "description": null,
  "remote": null
}
```

Reference (pulpcore): [Repository API Usage](https://docs.pulpproject.org/restapi.html#tag/repositories)



## Create a Distribution for Repository 'foo'

This will make the latest Repository Version content available for `ansible-galaxy` clients. Each
distribution names the url it can be accessed from on an attribute called `client_url`. The
`client_url` can be used with the `ansible-galaxy` client with the `-s` option. See the
`ansible-galaxy-roles-cli` docs for more details.

For example a distribution with `base_path` set to `my_content` could have a URL like:

```
http://pulp.example.com/pulp_ansible/galaxy/my_content/
```

```bash
# Distributions are created asynchronously. Create one, and specify the repository that will
# be served at the base path specified.
pulp ansible distribution create --name "baz" --base-path "my_content" --repository "foo"
```

Distribution create output:

```
Started background task /pulp/api/v3/tasks/48d187f6-d1d0-4d83-b803-dae9fe976da9/
.Done.
{
  "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/148ce745-3dd5-4dda-a0ba-f9c5ec7119e1/",
  "pulp_created": "2021-01-26T22:51:34.380612Z",
  "base_path": "my_content",
  "content_guard": null,
  "name": "baz",
  "repository": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/",
  "repository_version": null,
  "client_url": "http://pulp3-source-fedora31.localhost.example.com/pulp_ansible/galaxy/my_content/"
}
```

## Create a Distribution for a RepositoryVersion (optional)

Instead of always distributing the latest RepositoryVersion, you can also specify a specific
RepositoryVersion for a Distribution. This should be used in place of the distribution above, not in
addition to it.

```bash
# Distributions are created asynchronously. Create one, and specify the repository version that will
# be served at the base path specified.
pulp ansible distribution create --name "bar" --base-path "some_content" --repository "foo" --version 0
```

Distribution create output:

```
Started background task /pulp/api/v3/tasks/48d187f6-d1d0-4d83-b803-dae9fe976da9/
.Done.
{
  "pulp_href": "/pulp/api/v3/distributions/ansible/ansible/148ce745-3dd5-4dda-a0ba-f9c5ec7119e1/",
  "pulp_created": "2021-01-26T22:51:34.380612Z",
  "base_path": "my_content",
  "content_guard": null,
  "name": "baz",
  "repository": null,
  "repository_version": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/",
  "client_url": "http://pulp3-source-fedora31.localhost.example.com/pulp_ansible/galaxy/my_content/"
}
```



## Create a Remote

Creating a Remote object informs Pulp about an external content source, which most commonly is
`https://galaxy.ansible.com/` or another `pulp_ansible` instance. In this case, we will be
syncing all Roles where `namespace=elastic` on Galaxy. You can browse those Roles Pulp will import
[here](https://galaxy.ansible.com/api/v1/roles/?namespace=elastic).

```bash
# Create a remote that syncs some versions of django into your repository.
pulp ansible remote -t "role" create --name "bar" --url "https://galaxy.ansible.com/api/v1/roles/?owner__username=elastic"
```

Remote create output:

```
{
  "pulp_href": "/pulp/api/v3/remotes/ansible/role/38f37de9-842c-4690-a73c-9e813853b28b/",
  "pulp_created": "2021-01-26T22:55:17.126745Z",
  "name": "bar",
  "url": "https://galaxy.ansible.com/api/v1/roles/?owner__username=elastic",
  "ca_cert": null,
  "client_cert": null,
  "client_key": null,
  "tls_validation": true,
  "proxy_url": null,
  "username": null,
  "password": null,
  "pulp_last_updated": "2021-01-26T22:55:17.126755Z",
  "download_concurrency": 10,
  "policy": "immediate",
  "total_timeout": null,
  "connect_timeout": null,
  "sock_connect_timeout": null,
  "sock_read_timeout": null
}
```



## Sync Repository foo with Remote

Use the Remote object to kick off a synchronize task by specifying the Repository to
sync with. You are telling Pulp to fetch content from the Remote and add to the Repository.

```bash
# Sync repository foo using remote bar
pulp ansible repository sync --name "foo" --remote "role:bar"

# Use the -b option to have the sync task complete in the background
# e.g. pulp -b ansible repository sync --name "foo" --remote "bar"

# After the task is complete, it gives us a new repository version
# Inspecting new repository version
pulp ansible repository version show --repository "foo" --version 1
```

Repository Version show output:

```
{
    "pulp_href": "/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/",
    "pulp_created": "2021-01-26T22:57:55.451200Z",
    "number": 1,
    "base_version": null,
    "content_summary": {
      "added": {
        "ansible.role": {
          "count": 56,
          "href": "/pulp/api/v3/content/ansible/roles/?repository_version_added=/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/"
        }
      },
      "removed": {},
      "present": {
        "ansible.role": {
          "count": 56,
          "href": "/pulp/api/v3/content/ansible/roles/?repository_version=/pulp/api/v3/repositories/ansible/ansible/b17950e8-cee8-493a-b735-0d04905cf067/versions/1/"
        }
      }
    }
}
```

Reference (pulpcore): [Repository Version List API Usage](https://docs.pulpproject.org/restapi.html#operation/repositories_versions_list)



## Install a Role, hosted by Pulp, using `ansible-galaxy`

### Using a direct path

Install your role by name by specifying the distribution serving your Repository's content using the
`-s` option.

`ansible-galaxy install elasticsearch,6.2.4 -c -s http://pulp.example.com/pulp_ansible/galaxy/my_content/`

### Configuring ansible-galaxy Permanently

Use the [ansible-galaxy config files](https://docs.ansible.com/ansible/latest/cli/ansible-galaxy.html#environment) to specify the distribution `ansible-galaxy` should interact
with. To use this, set up your distribution in your ansible config (e.g. `~/.ansible.cfg` or
`/etc/ansible/ansible.cfg`):

```
[galaxy]
server: http://pulp.example.com/pulp_ansible/galaxy/my_content/
```

Then you can install without the `-s` url

```bash
$ ansible-galaxy install elastic.elasticsearch,6.2.4
- downloading role 'elasticsearch', owned by elastic
- downloading role from http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
- extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
- elastic.elasticsearch (6.2.4) was installed successfully
```
