# Create a remote that syncs some versions of django into your repository.
http POST $BASE_ADDR/pulp/api/v3/remotes/python/python/ \
    name='bar' \
    url='https://galaxy.ansible.com/api/v1/roles/?namespace__name=elastic'

# Export an environment variable for the new remote URI.
export REMOTE_HREF=$(http $BASE_ADDR/pulp/api/v3/remotes/python/python/ | jq -r '.results[] | select(.name == "bar") | ._href')

# Lets inspect our newly created Remote
http $BASE_ADDR$REMOTE_HREF
