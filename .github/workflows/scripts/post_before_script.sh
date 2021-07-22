#!/usr/bin/env sh

echo "machine pulp
login admin
password password
" > ~/.netrc

chmod og-rw ~/.netrc

PG_CONF_PATH=$(docker exec -u postgres pulp psql -c 'SHOW config_file' | grep '\.conf' | xargs)
docker exec -u postgres pulp sed -i 's/max_connections = 100/max_connections = 1024/g' $PG_CONF_PATH
docker exec pulp bash -c "s6-svc -d /var/run/s6/services/pulpcore-api"
sleep 5
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/postgresql"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/pulpcore-content"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/pulpcore-resource-manager"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/pulpcore-worker@1"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/pulpcore-worker@2"
docker exec pulp bash -c "s6-svc -u /var/run/s6/services/pulpcore-api"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/new-pulpcore-resource-manager"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/new-pulpcore-worker@1"
docker exec pulp bash -c "s6-svc -r /var/run/s6/services/new-pulpcore-worker@2"
echo "Restarting postgres in 60 seconds"
sleep 60
