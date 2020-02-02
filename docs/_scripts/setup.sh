export BASE_ADDR=http://localhost:24817
export CONTENT_ADDR=http://localhost:24816

wait_for_pulp() {
  unset CREATED_RESOURCE
  local task_url=$1
  while [ -z "$CREATED_RESOURCE" ]

  do
    sleep 4
    export CREATED_RESOURCE=$(http $BASE_ADDR$task_url | jq -r '.created_resources | first')
  done
}

sudo dnf install jq httpie -y
