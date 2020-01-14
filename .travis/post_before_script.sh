#!/usr/bin/env bash

set -euv

cd ../pulp-openapi-generator

./generate.sh pulpcore python
pip install ./pulpcore-client
./generate.sh pulp_ansible python
pip install ./pulp_ansible-client
