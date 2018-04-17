#!/usr/bin/env sh
set -v

flake8 --config flake8.cfg || exit 1

result=0

pulp-manager migrate auth --noinput
pulp-manager makemigrations pulp_app --noinput
pulp-manager makemigrations pulp_ansible
pulp-manager migrate --noinput
if [ $? -ne 0 ]; then
  result=1
fi
pulp-manager reset-admin-password --password admin
pulp-manager runserver >>~/django_runserver.log 2>&1 &
celery worker -A pulpcore.tasking.celery_app:celery -n resource_manager@%h -Q resource_manager -c 1 --events --umask 18 >>~/resource_manager.log 2>&1 &
celery worker -A pulpcore.tasking.celery_app:celery -n reserved_resource_worker_1@%h -c 1 --events --umask 18 >>~/reserved_workers-1.log 2>&1 &
sleep 5
py.test -v --color=yes --pyargs ./pulp_ansible/tests/functional/
if [ $? -ne 0 ]; then
  result=1
fi

cat ~/django_runserver.log
cat ~/resource_manager.log
cat ~/reserved_workers-1.log

exit $result
