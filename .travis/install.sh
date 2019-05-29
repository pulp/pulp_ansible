#!/usr/bin/env sh
set -v

# Run Ansible playbook
cd ../ansible-pulp
ansible-galaxy install -r requirements.yml

ansible-playbook --connection=local --inventory 127.0.0.1, playbook.yml --extra-vars \
  "pulp_python_interpreter=$VIRTUAL_ENV/bin/python, pulp_install_dir=$VIRTUAL_ENV \
  pulp_db_type=$DB"
