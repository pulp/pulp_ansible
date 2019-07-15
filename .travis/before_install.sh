#!/usr/bin/env bash

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by bootstrap.py. Please use
# bootstrap.py to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -mveuo pipefail

export PRE_BEFORE_INSTALL=$TRAVIS_BUILD_DIR/.travis/pre_before_install.sh
export POST_BEFORE_INSTALL=$TRAVIS_BUILD_DIR/.travis/post_before_install.sh

COMMIT_MSG=$(git log --format=%B --no-merges -1)
export COMMIT_MSG

if [ -x $PRE_BEFORE_INSTALL ]; then
    $PRE_BEFORE_INSTALL
fi

export PULP_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulpcore\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_PLUGIN_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulpcore-plugin\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_SMASH_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/PulpQE\/pulp-smash\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_ROLES_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/ansible-pulp\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_BINDINGS_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp-openapi-generator\/pull\/(\d+)' | awk -F'/' '{print $7}')

# dev_requirements should not be needed for testing; don't install them to make sure
pip install -r test_requirements.txt

# check the commit message
./.travis/check_commit.sh

# run black separately from flake8 to get a diff
black --check --diff .

# Lint code.
flake8 --config flake8.cfg

cd ..
git clone --depth=1 https://github.com/pulp/ansible-pulp.git
if [ -n "$PULP_ROLES_PR_NUMBER" ]; then
  cd ansible-pulp
  git fetch --depth=1 origin +refs/pull/$PULP_ROLES_PR_NUMBER/merge
  git checkout FETCH_HEAD
  cd ..
fi

git clone --depth=1 https://github.com/pulp/pulpcore.git

if [ -n "$PULP_PR_NUMBER" ]; then
  cd pulpcore
  git fetch --depth=1 origin +refs/pull/$PULP_PR_NUMBER/merge
  git checkout FETCH_HEAD
  cd ..
fi


git clone --depth=1 https://github.com/pulp/pulpcore-plugin.git

if [ -n "$PULP_PLUGIN_PR_NUMBER" ]; then
  cd pulpcore-plugin
  git fetch --depth=1 origin +refs/pull/$PULP_PLUGIN_PR_NUMBER/merge
  git checkout FETCH_HEAD
  cd ..
fi


if [ -n "$PULP_SMASH_PR_NUMBER" ]; then
  git clone --depth=1 https://github.com/PulpQE/pulp-smash.git
  cd pulp-smash
  git fetch --depth=1 origin +refs/pull/$PULP_SMASH_PR_NUMBER/merge
  git checkout FETCH_HEAD
  cd ..
fi

psql -c 'CREATE DATABASE pulp OWNER travis;'

pip install ansible
cp pulp_ansible/.travis/playbook.yml ansible-pulp/playbook.yml
cp pulp_ansible/.travis/postgres.yml ansible-pulp/postgres.yml

cd pulp_ansible

if [ -x $POST_BEFORE_INSTALL ]; then
    $POST_BEFORE_INSTALL
fi
