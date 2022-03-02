Galaxy API Refactor stage 1

- move the existing collection views under /plugin/ansible/
- redirects the legacy v3 endpoints to their counterparts in /plugin/ansible/
- adds a new configuration option ANSIBLE_DEFAULT_DISTRIBUTION_PATH that allows users to configure a default distribution base path for the API
- adds a new configuration option ANSIBLE_URL_NAMESPACE that allows django URL namespace to be set on reverse so that urls can be configured to point correctly to the galaxy APIs when pulp ansible is deployed as part of automation hub
- adds the get v3/artifacts/path/file API endpoint from galaxy_ng
- enable RedirectContentGuard

fixes: #728