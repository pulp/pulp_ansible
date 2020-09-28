Settings
========

`pulp_ansible` provides a few settings to control various features. These settings are settable
with dynaconf in various as a regular Pulp setting. See the `pulpcore Setting <https://docs.
pulpproject.org/en/3.0/nightly/installation/configuration.html#configuration>`_.


ANSIBLE_API_HOSTNAME
^^^^^^^^^^^^^^^^^^^^
   The origin, e.g. "http://example.com" that will instruct the client how to find the Pulp API
   service. This URL is formed in various Galaxy APIs (V1, V2, V3) responses.

   This defaults to http on your fqdn, which is usable with the Ansible installer's default Nginx
   configuration. So if `example.com` is your fqdn, this would default to "http://example.com".


ANSIBLE_CONTENT_HOSTNAME
^^^^^^^^^^^^^^^^^^^^^^^^

   The origin, e.g. "http://example.com" that will instruct the client how to find the Pulp content
   app. This URL is formed in various Galaxy APIs (V1, V2, V3) responses.

   This defaults to `CONTENT_ORIGIN <https://docs.pulpproject.org/pulpcore/settings.html?#content-origin>`_.
   By default it includes the ``pulp/content`` subpath. So if `https://example.com` is your
   CONTENT_ORIGIN, this would default to "https://example.com/pulp/content".


GALAXY_API_ROOT
^^^^^^^^^^^^^^^

   By default the Galaxy V1, V2, and V3 APIs are rooted at
   "/pulp_ansible/galaxy/<path:path>/api/", but this is configurable. Specifying `GALAXY_API_ROOT`
   will re-root the Galaxy API to a different URL namespace.

   The `<path:path>` must be included, which corresponds to the `base_path` of an
   `Ansible Distribution`. Clients using the Galaxy API will only receive content served by that
   `Ansible Distribution`.
