def test_repository_in_domain(ansible_bindings, domain_factory, ansible_repository_factory):
    domain = domain_factory()
    ansible_repository = ansible_repository_factory(pulp_domain=domain.name)
    result = ansible_bindings.RepositoriesAnsibleApi.list(name=ansible_repository.name)
    assert result.count == 0
    result = ansible_bindings.RepositoriesAnsibleApi.list(
        pulp_domain=domain.name, name=ansible_repository.name
    )
    assert result.count == 1
