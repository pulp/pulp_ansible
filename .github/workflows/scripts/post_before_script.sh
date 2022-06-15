#!/usr/bin/env sh

set -euv

echo "machine pulp
login admin
password password
" > ~/.netrc

chmod og-rw ~/.netrc

if [[ "$TEST" == "upgrade" ]]; then
    exit
fi
