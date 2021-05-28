#!/bin/sh
set -e

curl -s -X POST https://api.github.com/repos/$GITHUB_REPOSITORY/git/refs \
-H "Authorization: token $GITHUB_TOKEN" \
-d @- << EOF
{
  "ref": "refs/tags/$1",
  "sha": "$2"
}
EOF
