# Settings

`pulp_ansible` provides a few settings to control various features. These settings are settable
with dynaconf in various as a regular Pulp setting. See the [pulpcore Setting](https://docs.pulpproject.org/en/3.0/nightly/installation/configuration.html#configuration).

## ANSIBLE_API_HOSTNAME

> The origin, e.g. "<http://example.com>" that will instruct the client how to find the Pulp API
> service. This URL is formed in various Galaxy APIs (V1, V2, V3) responses.
>
> This defaults to http on your fqdn, which is usable with the Ansible installer's default Nginx
> configuration. So if `example.com` is your fqdn, this would default to "<http://example.com>".

## ANSIBLE_CONTENT_HOSTNAME

> The origin, e.g. "<http://example.com>" that will instruct the client how to find the Pulp content
> app. This URL is formed in various Galaxy APIs (V1, V2, V3) responses.
>
> This defaults to [CONTENT_ORIGIN](https://docs.pulpproject.org/pulpcore/settings.html?#content-origin).
> By default it includes the `pulp/content` subpath. So if `https://example.com` is your
> CONTENT_ORIGIN, this would default to "<https://example.com/pulp/content>".

## ANSIBLE_SIGNATURE_REQUIRE_VERIFICATION

> By default, `pulp_ansible` rejects uploaded signatures if they cannot be verified against a
> public key specified on the repository. Setting this to false will allow accepting signatures
> if no key was specified. A repository with a configured key will always reject invalid
> signatures.

## ANSIBLE_SIGNING_TASK_LIMITER

> This number determines the amount of concurrent signing processes that can be spawned at one time
> during a signature task. Increasing this number will generally increase the speed of the task, but
> will also consume more resources of the worker. Defaults to 10 concurrent processes.

## GALAXY_API_ROOT

> By default the Galaxy V1, V2, and V3 APIs are rooted at
> "/pulp_ansible/galaxy/\<path:path>/api/", but this is configurable. Specifying `GALAXY_API_ROOT`
> will re-root the Galaxy API to a different URL namespace.
>
> The `<path:path>` must be included, which corresponds to the `base_path` of an
> `Ansible Distribution`. Clients using the Galaxy API will only receive content served by that
> `Ansible Distribution`.

## ANSIBLE_DEFAULT_DISTRIBUTION_PATH

> Set the distribution base path to be used on the `GALAXY_API_ROOT/default/api/` endpoint.
> By default, this is set to `None`, which causes the API to return a 404 on the `default`
> endpoint.

## ANSIBLE_URL_NAMESPACE

> The Django URL namespace to be used when generating URLs that are returned by the galaxy
> APIs. Setting this allows for the Galaxy APIs to redirect requests to django URLs in other apps.
> This defaults to the pulp ansible URL router.

## ANSIBLE_COLLECT_DOWNLOAD_LOG

> A flag to activate collecting download logs about collections consumed. You can dump the
> collected information using `pulpcore-manager download-log`.

## ANSIBLE_AUTHENTICATION_CLASSES

> A list of authentication classes to be used to authenticate requests to the Galaxy API. Defaults
> to `REST_FRAMEWORK__DEFAULT_AUTHENTICATION_CLASSES`. See [authentication docs](https://www.django-rest-framework.org/api-guide/authentication/#api-reference) for more.

## ANSIBLE_PERMISSION_CLASSES

> A list of permission classes to be used to authorize requests to the Galaxy API. Defaults to
> `REST_FRAMEWORK__DEFAULT_PERMISSION_CLASSES`. See [authorization docs](https://www.django-rest-framework.org/api-guide/permissions/#api-reference) for more.
