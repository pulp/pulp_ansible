#!/usr/bin/env sh
set -v

mkdir -p ~/.config/pulp_smash
cp ../pulpcore/.travis/pulp-smash-config.json ~/.config/pulp_smash/settings.json
