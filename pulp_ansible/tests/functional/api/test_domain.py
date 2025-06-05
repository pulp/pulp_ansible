import string
import random
import pytest
import requests


@pytest.mark.parallel
def test_repository_in_domain(ansible_bindings, domain_factory, ansible_repository_factory):
    domain = domain_factory()
    repository = ansible_repository_factory(pulp_domain=domain.name)
    result = ansible_bindings.RepositoriesAnsibleApi.list(name=repository.name)
    assert result.count == 0
    result = ansible_bindings.RepositoriesAnsibleApi.list(
        pulp_domain=domain.name, name=repository.name
    )
    assert result.count == 1


@pytest.mark.parallel
class TestBasePathIsScopedToDomain:
    domain = "".join(random.sample(string.ascii_lowercase, 12))
    base_path = "".join(random.sample(string.ascii_lowercase, 12))

    @pytest.fixture(scope="class")
    def default_distribution(
        self,
        ansible_repository_factory,
        ansible_distribution_factory,
    ):
        return ansible_distribution_factory(
            base_path=self.base_path,
            repository=ansible_repository_factory(),
        )

    @pytest.fixture(scope="class")
    def domain_distribution(
        self,
        domain_factory,
        ansible_repository_factory,
        ansible_distribution_factory,
    ):
        domain = domain_factory(name=self.domain)
        return ansible_distribution_factory(
            pulp_domain=domain.name,
            base_path=self.base_path,
            repository=ansible_repository_factory(pulp_domain=domain.name),
        )

    def test_default_client_url_can_be_reached(
        self,
        bindings_cfg,
        default_distribution,
    ):
        auth = (bindings_cfg.username, bindings_cfg.password)
        response = requests.get(default_distribution.client_url + "api/v3/", auth=auth)
        response.raise_for_status()

    def test_domain_client_url_can_be_reached(
        self,
        bindings_cfg,
        domain_distribution,
    ):
        auth = (bindings_cfg.username, bindings_cfg.password)
        response = requests.get(domain_distribution.client_url + "api/v3/", auth=auth)
        response.raise_for_status()

    def test_client_url_contains_domain(
        self,
        bindings_cfg,
        default_distribution,
        domain_distribution,
    ):
        assert default_distribution.client_url != domain_distribution.client_url
        assert self.domain in domain_distribution.client_url
