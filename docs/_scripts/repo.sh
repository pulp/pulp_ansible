# Start by creating a new repository named "foo":
http POST $BASE_ADDR/pulp/api/v3/repositories/ansible/ansible/ name=foo

# If you want to copy/paste your way through the guide,
# create an environment variable for the repository URI.
export REPO_HREF=$(http $BASE_ADDR/pulp/api/v3/repositories/ansible/ansible/ | \
  jq -r '.results[] | select(.name == "foo") | .pulp_href')

# Lets inspect our newly created repository.
http $BASE_ADDR$REPO_HREF
