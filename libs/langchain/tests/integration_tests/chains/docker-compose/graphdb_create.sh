#! /bin/bash
REPOSITORY_ID="langchain"
GRAPHDB_URI="http://localhost:7200/"

echo -e "\nUsing GraphDB: ${GRAPHDB_URI}"

function startGraphDB {
 echo -e "\nStarting GraphDB..."
 exec /opt/graphdb/dist/bin/graphdb
}

function waitGraphDBStart {
  echo -e "\nWaiting GraphDB to start..."
  for i in $(seq 1 5); do
    CHECK_RES=$(curl --silent --write-out '%{http_code}' --output /dev/null ${GRAPHDB_URI}/rest/repositories)
    if [ "${CHECK_RES}" = '200' ]; then
        echo -e "\nUp and running"
        break
    fi
    sleep 30s
    echo "CHECK_RES: ${CHECK_RES}"
  done
}

function loadData {
  echo -e "\nImporting berners-lee-card.ttl"
  curl -X POST -H "Content-Type:application/x-turtle" -T /berners-lee-card.ttl  ${GRAPHDB_URI}/repositories/${REPOSITORY_ID}/statements
}

startGraphDB &
waitGraphDBStart
loadData
wait
