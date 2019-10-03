#!/bin/bash

if [ "$TRAVIS_EVENT_TYPE" = "cron" ]; then
  echo "--- Performance Tests ---"
  pytest -vv -r sx --color=yes --pyargs --durations=0 pulp_ansible.tests.performance
