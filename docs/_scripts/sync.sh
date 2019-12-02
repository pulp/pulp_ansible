# Using the Remote we just created, we kick off a sync task
export TASK_URL=$(http POST $BASE_ADDR$REPO_HREF'sync/' remote=$REMOTE_HREF \
  | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
# When the task is complete, it gives us a new repository version
wait_for_pulp $TASK_URL
export REPOVERSION_HREF=${CREATED_RESOURCE[0]}

# Lets inspect our newly created RepositoryVersion
http $BASE_ADDR$REPOVERSION_HREF
