#!/usr/bin/env bash
# coding=utf-8

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by bootstrap.py. Please use
# bootstrap.py to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -mveuo pipefail

export POST_SCRIPT=$TRAVIS_BUILD_DIR/.travis/post_script.sh
export POST_DOCS_TEST=$TRAVIS_BUILD_DIR/.travis/post_docs_test.sh
export FUNC_TEST_SCRIPT=$TRAVIS_BUILD_DIR/.travis/func_test_script.sh

# Needed for both starting the service and building the docs.
# Gets set in .travis/settings.yml, but doesn't seem to inherited by
# this script.
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings

if [ "$TEST" = 'docs' ]; then
  cd docs
  make html
  cd ..

  if [ -f $POST_DOCS_TEST ]; then
      $POST_DOCS_TEST
  fi
  exit
fi

if [ "$TEST" = 'bindings' ]; then
  COMMIT_MSG=$(git log --format=%B --no-merges -1)
  export PULP_BINDINGS_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp-openapi-generator\/pull\/(\d+)' | awk -F'/' '{print $7}')

  cd ..
  git clone https://github.com/pulp/pulp-openapi-generator.git
  cd pulp-openapi-generator

  if [ -n "$PULP_BINDINGS_PR_NUMBER" ]; then
    git fetch origin +refs/pull/$PULP_BINDINGS_PR_NUMBER/merge
    git checkout FETCH_HEAD
  fi

  ./generate.sh pulpcore python
  pip install ./pulpcore-client
  ./generate.sh pulp_ansible python
  pip install ./pulp_ansible-client

  python $TRAVIS_BUILD_DIR/.travis/test_bindings.py

  if [ ! -f $TRAVIS_BUILD_DIR/.travis/test_bindings.rb ]
  then
    exit
  fi

  rm -rf ./pulpcore-client

  ./generate.sh pulpcore ruby
  cd pulpcore-client
  gem build pulpcore_client
  gem install --both ./pulpcore_client-0.gem
  cd ..

  rm -rf ./pulp_ansible-client

  ./generate.sh pulp_ansible ruby

  cd pulp_ansible-client
  gem build pulp_ansible_client
  gem install --both ./pulp_ansible_client-0.gem
  cd ..

  ruby $TRAVIS_BUILD_DIR/.travis/test_bindings.rb
  exit
fi

# Aliases for running commands in the pulp-api container.
export PULP_API_POD=$(sudo kubectl get pods | grep -E -o "pulp-api-(\w+)-(\w+)")
# Run a command
export CMD_PREFIX="sudo kubectl exec $PULP_API_POD --"
# Run a command, and pass STDIN
export CMD_STDIN_PREFIX="sudo kubectl exec -i $PULP_API_POD --"
# The alias does not seem to work in Travis / the scripting framework
#alias pytest="$CMD_PREFIX pytest"

# Run unit tests.
$CMD_PREFIX bash -c "PULP_DATABASES__default__USER=postgres django-admin test --noinput /usr/local/lib/python${TRAVIS_PYTHON_VERSION}/site-packages/pulp_ansible/tests/unit/"

# Note: This function is in the process of being merged into after_failure
show_logs_and_return_non_zero() {
  readonly local rc="$?"
  return "${rc}"
}
export -f show_logs_and_return_non_zero

# Run functional tests
set +u

export PYTHONPATH=$TRAVIS_BUILD_DIR:$TRAVIS_BUILD_DIR/../pulpcore:${PYTHONPATH}

set -u

if [[ "$TEST" == "performance" ]]; then
  echo "--- Performance Tests ---"
  pytest -vv -r sx --color=yes --pyargs --capture=no --durations=0 pulp_ansible.tests.performance || show_logs_and_return_non_zero
  exit
fi

if [ -f $FUNC_TEST_SCRIPT ]; then
    $FUNC_TEST_SCRIPT
else
    pytest -v -r sx --color=yes --pyargs pulp_ansible.tests.functional || show_logs_and_return_non_zero
fi

if [ -f $POST_SCRIPT ]; then
    $POST_SCRIPT
fi
