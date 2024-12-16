#!/bin/bash

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --github pulp_ansible' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -euv

# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")/../../.."

VERSION="$1"

if [[ -z "${VERSION}" ]]
then
  echo "No version specified."
  exit 1
fi

twine upload -u __token__ -p "${PYPI_API_TOKEN}" \
"dist/pulp_ansible_client-${VERSION}-py3-none-any.whl" \
"dist/pulp_ansible-client-${VERSION}.tar.gz" \
;
