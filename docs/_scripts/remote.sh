#!/bin/bash -e
#!/usr/bin/env bash

# Create a remote that syncs some versions of django into your repository.
pulp ansible remote -t "role" create --name "bar" --url "https://galaxy.ansible.com/api/v1/roles/?namespace__name=elastic"
