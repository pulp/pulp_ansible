#!/usr/bin/env bash
# coding=utf-8

set -mveuo pipefail

pytest -v -r sx --color=yes --pyargs pulp_ansible.tests.functional || show_logs_and_return_non_zero

if [ "$GITHUB_WORKFLOW" = "Pulp Nightly CI/CD" ] && ["$TEST" == "s3" ]
then
    pytest -v -r sx --color=yes --pyargs galaxy_ng.tests.functional || show_logs_and_return_non_zero
fi
