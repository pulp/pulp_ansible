def test_client_config_distro(
    ansible_repo, ansible_distribution_factory, ansible_client_configuration_api_client
):
    distro = ansible_distribution_factory(ansible_repo)
    res = ansible_client_configuration_api_client.get(path=distro.base_path)
    assert res.default_distribution_path == distro.base_path


def test_client_config_default_distro(
    ansible_repo, ansible_distribution_factory, ansible_client_default_configuration_api_client
):
    res = ansible_client_default_configuration_api_client.get()
    assert res.default_distribution_path is None
