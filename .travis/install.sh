#!/usr/bin/env sh
set -v

export COMMIT_MSG=$(git show HEAD^2 -s)
export PULP_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_SMASH_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/PulpQE\/pulp-smash\/pull\/(\d+)' | awk -F'/' '{print $7}')

pip install flake8 pytest

# temporary workaround until a newer RQ release is available
pip install git+https://github.com/rq/rq.git@3133d94b58e59cb86e8f4677492d48b2addcf5f8

cd .. && git clone https://github.com/pulp/pulp.git

if [ -z $PULP_PR_NUMBER ]; then
  pushd pulp && git checkout 3.0-dev && popd
else
  export PULP_SHA=$(curl https://api.github.com/repos/pulp/pulp/pulls/$PULP_PR_NUMBER | jq -r '.merge_commit_sha')
  pushd pulp
  git fetch origin +refs/pull/$PULP_PR_NUMBER/merge
  git checkout $PULP_SHA
  popd
fi

pushd pulp/common/ && pip install -e . && popd
pushd pulp/pulpcore/ && pip install -e . && popd
pushd pulp/plugin/ && pip install -e .  && popd

if [ -z $PULP_SMASH_PR_NUMBER ]; then
  pip install git+https://github.com/PulpQE/pulp-smash.git#egg=pulp-smash
else
  export PULP_SMASH_SHA=$(curl https://api.github.com/repos/PulpQE/pulp-smash/pulls/$PULP_SMASH_PR_NUMBER | jq -r '.merge_commit_sha')
  git clone https://github.com/PulpQE/pulp-smash.git
  pushd pulp-smash
  git fetch origin +refs/pull/$PULP_SMASH_PR_NUMBER/merge
  git checkout $PULP_SMASH_SHA
  pip install -e . && popd
fi

cd pulp_ansible
pip install -e .
