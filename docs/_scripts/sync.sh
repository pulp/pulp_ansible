#!/usr/bin/env bash

# Sync repository foo using remote bar
echo "Create a task to sync the repository using the remote."
export TASK_HREF=$(http POST $BASE_ADDR$REPO_HREF'sync/' \
    remote=$REMOTE_HREF \
    | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_HREF

# After the task is complete, it gives us a new repository version
echo "Set REPOVERSION_HREF from finished task."
export REPOVERSION_HREF=$(http $BASE_ADDR$TASK_HREF| jq -r '.created_resources | first')

echo "Inspecting RepositoryVersion."
http $BASE_ADDR$REPOVERSION_HREF