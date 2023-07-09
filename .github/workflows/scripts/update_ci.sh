#!/usr/bin/env bash
# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --github pulp_ansible' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -eu

if [ ! -f "template_config.yml" ]; then
  echo "No template_config.yml detected."
  exit 1
fi

pushd ../plugin_template
./plugin-template --github pulp_ansible
popd

# Check if only gitref file has changed, so no effect on CI workflows.
if [ "$(git diff --name-only | grep -v "template_gitref")" ]; then
  echo "No changes detected."
  git restore ".github/template_gitref" "docs/template_gitref"
fi

if [[ $(git status --porcelain) ]]; then
  git add -A
  git commit -m "Update CI files" -m "[noissue]"
else
  echo "No updates needed"
fi
