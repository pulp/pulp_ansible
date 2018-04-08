#!/usr/bin/env sh
set -v

flake8 --config flake8.cfg || exit 1
