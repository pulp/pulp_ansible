#!/usr/bin/env bash

if [ "$GITHUB_WORKFLOW" = "Pulp Nightly CI/CD" ] && ["$TEST" == "s3" ]
then
    # Removing pulpcore and pulp-ansible restrictions:
    sed -i '0,/pulp-ansible/{s/pulp-ansible.*/pulp-ansible",/}' ../galaxy_ng/setup.py
    sed -i '0,/pulpcore/{s/pulpcore.*/pulpcore",/}' ../galaxy_ng/setup.py
fi
