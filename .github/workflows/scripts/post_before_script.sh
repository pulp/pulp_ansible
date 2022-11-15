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

cmd_user_stdin_prefix bash -c "cat > /var/lib/pulp/sign-metadata.sh" < "$GITHUB_WORKSPACE"/pulp_ansible/tests/assets/sign-metadata.sh

cmd_user_prefix bash -c "curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | gpg --import"
cmd_user_prefix bash -c "curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-pulp-qe | cat > /tmp/GPG-KEY-pulp-qe"
cmd_user_prefix chmod a+x /var/lib/pulp/sign-metadata.sh

KEY_FINGERPRINT="6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
TRUST_LEVEL="6"
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | cmd_user_stdin_prefix gpg --import-ownertrust

curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-PRIVATE-KEY-pulp-qe | gpg --import
curl -L https://github.com/pulp/pulp-fixtures/raw/master/common/GPG-KEY-pulp-qe | cat > /tmp/GPG-KEY-pulp-qe
echo "$KEY_FINGERPRINT:$TRUST_LEVEL:" | gpg --import-ownertrust
export TEST_PULP_SIGNING_SCRIPT="$GITHUB_WORKSPACE"/pulp_ansible/tests/assets/sign-metadata.sh
