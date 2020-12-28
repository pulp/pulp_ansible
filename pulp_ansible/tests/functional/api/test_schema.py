import schemathesis
from hypothesis import settings, target
from pulp_smash import config


cfg = config.get_config()
base_url = cfg.get_base_url()
schema = schemathesis.from_uri(f"{base_url}/pulp/api/v3/docs/api.json?plugin=pulp_ansible")


@schema.parametrize()
@settings(deadline=1100)
def test_time(case):
    """Test response time."""
    response = case.call()
    target(response.elapsed.total_seconds())
    assert response.elapsed.total_seconds() < 1.1


# @schema.parametrize()
# def test_api(case):
#   """Test and validate API."""
#   # Ideally we would run:
#     case.call_and_validate()
#   # But validation is breaking because we need to provide some data e.g. distribution base_path
# https://schemathesis.readthedocs.io/en/stable/stateful.html?#how-to-provide-initial-data-for-test-scenarios
#     assert 1 == 1
