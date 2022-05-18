#!/usr/bin/env sh

set -euv

# Add the QE (public) key to the container env for `test_sign_locally_then_upload_signature`.
# Please, remove once the verification was made independent of the system keyring.

cmd_prefix bash -c "curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-pulp-qe | gpg --import"

KEY_FINGERPRINT="6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
TRUST_LEVEL="6"
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | cmd_stdin_prefix gpg --import-ownertrust
