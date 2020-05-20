#!/usr/bin/env bash
echo "Setting environment variables for default hostname/port for the API and the Content app"
export BASE_ADDR=${BASE_ADDR:-http://localhost:24817}
export CONTENT_ADDR=${CONTENT_ADDR:-http://localhost:24816}

# Necessary for `django-admin`
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings

# Poll a Pulp task until it is finished.
wait_until_task_finished() {
    echo "Polling the task until it has reached a final state."
    local task_url=$1
    while true
    do
        local response=$(http $task_url)
        local state=$(jq -r .state <<< ${response})
        jq . <<< "${response}"
        case ${state} in
            failed|canceled)
                echo "Task in final state: ${state}"
                exit 1
                ;;
            completed)
                echo "$task_url complete."
                break
                ;;
            *)
                echo "Still waiting..."
                sleep 2
                ;;
        esac
    done
}
