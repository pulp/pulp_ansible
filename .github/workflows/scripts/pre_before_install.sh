#!/usr/bin/env bash

if [ "$GITHUB_WORKFLOW" = "Pulp Nightly CI/CD" ] && ["$TEST" == "s3" ]
then
    # Adding galaxy on nightly s3 jobs
    sed -i "s/additional_plugins: \[\]/additional_plugins: \[\{'name': 'galaxy_ng', 'branch': 'master', 'org': 'ansible'\}\]/g" template_config.yml
    cd ..
    git clone --depth=1 https://github.com/pulp/plugin_template.git
    cd plugin_template
    ./plugin-template --github pulp_ansible
    cd ../pulp_ansible
fi
