# Create a remote that syncs some versions of django into your repository.
http POST $BASE_ADDR/pulp/api/v3/remotes/ansible/collection/ \
    name='bar' \
    auth_url='https://sso.qa.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token' \
    token=$ANSIBLE_TOKEN_AUTH \
    tls_validation=false \
    url='https://cloud.redhat.com/api/automation-hub' \
    requirements_file:='"collections:\n  - testing.ansible_testing_content"'

# Export an environment variable for the new remote URI.
export REMOTE_HREF=$(http $BASE_ADDR/pulp/api/v3/remotes/ansible/collection/ | jq -r '.results[] | select(.name == "bar") | .pulp_href')

# Lets inspect our newly created Remote
http $BASE_ADDR$REMOTE_HREF
