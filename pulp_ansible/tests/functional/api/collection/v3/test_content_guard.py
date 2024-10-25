import requests

# Using requests for these tests because the client follows redirects and I need to inspect the URL
# that gets redirected to


def _get_download_url(ansible_bindings, distribution, namespace, name):
    collection_api = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexApi
    versions_api = (
        ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleContentCollectionsIndexVersionsApi
    )

    collection = collection_api.read(
        distribution.base_path,
        name,
        namespace,
    )

    version = versions_api.read(
        distribution.base_path, name, namespace, collection.highest_version["version"]
    )

    return version.download_url


def test_download(
    skip_on_galaxy,
    bindings_cfg,
    ansible_bindings,
    ansible_repo_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Test that downloads without content guards work correctly."""
    # Setup distribution
    repository = ansible_repo_factory()
    collection, collection_href = build_and_upload_collection(repository)
    distribution = ansible_distribution_factory(repository=repository)

    # Fetch content
    download_url = _get_download_url(
        ansible_bindings, distribution, collection.namespace, collection.name
    )
    pulp_auth = (bindings_cfg.username, bindings_cfg.password)
    response = requests.get(download_url, auth=pulp_auth, allow_redirects=False)

    # Verify that the download url redirects to the content app
    assert response.is_redirect
    content_app_url = response.headers["Location"]

    # Verify that the collection can be downloaded without authentication
    assert "validate_token" not in content_app_url

    response = requests.get(content_app_url)
    assert response.status_code == 200


def test_download_with_content_guard(
    pulpcore_bindings,
    ansible_bindings,
    bindings_cfg,
    gen_object_with_cleanup,
    ansible_repo_factory,
    ansible_distribution_factory,
    build_and_upload_collection,
):
    """Test that downloads with content guards work correctly."""
    # Setup content guarded distribution
    guard = gen_object_with_cleanup(
        pulpcore_bindings.ContentguardsContentRedirectApi, {"name": "test-content-guard"}
    )
    repository = ansible_repo_factory()
    collection, collection_href = build_and_upload_collection(repository)
    distribution = ansible_distribution_factory(
        repository=repository, content_guard=guard.pulp_href
    )

    # Fetch content
    download_url = _get_download_url(
        ansible_bindings, distribution, collection.namespace, collection.name
    )
    pulp_auth = (bindings_cfg.username, bindings_cfg.password)
    response = requests.get(download_url, auth=pulp_auth, allow_redirects=False)

    # Verify that the download url redirects to the content app
    assert response.is_redirect
    content_app_url = response.headers["Location"]

    # Verify that token is present
    assert "validate_token" in content_app_url

    collection = requests.get(content_app_url)
    assert collection.status_code == 200

    # Perform an unauthenticated call to the content app and verify that it gets rejected
    collection = requests.get(content_app_url.split("?")[0])
    assert collection.status_code == 403
