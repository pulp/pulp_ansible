# Distributions are created asynchronously. Create one, and specify the publication that will
# be served at the base path specified.
export TASK_URL=$(http POST $BASE_ADDR/pulp/api/v3/distributions/ansible/ansible/ \
  name='baz' \
  base_path='my_content' \
  repository=${REPO_HREF} | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
# When the task is complete, it gives us the href for our new Distribution
wait_for_pulp $TASK_URL
export DIST_PATH=${CREATED_RESOURCE[0]}

# Lets inspect the Distribution
http $BASE_ADDR$DIST_PATH
