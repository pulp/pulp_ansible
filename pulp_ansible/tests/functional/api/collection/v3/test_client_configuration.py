import pytest


@pytest.mark.parallel
def test_client_config_distro(ansible_bindings, ansible_repo_factory, ansible_distribution_factory):
    distribution = ansible_distribution_factory(ansible_repo_factory())
    response = ansible_bindings.PulpAnsibleApiV3PluginAnsibleClientConfigurationApi.read(
        path=distribution.base_path
    )
    assert response.default_distribution_path == distribution.base_path


@pytest.mark.parallel
def test_client_config_default_distro(ansible_bindings):
    response = ansible_bindings.PulpAnsibleDefaultApiV3PluginAnsibleClientConfigurationApi.read()
    assert response.default_distribution_path is None
