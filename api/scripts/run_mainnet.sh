#!/bin/sh
# Runs the mainnet API and starts it again if it stops (for example when the network drops during startup).
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env.mainnet; set +a
while true; do
  .venv/bin/python -m humanapi_api >> data/mainnet.log 2>&1
  echo "$(date) server stopped; starting again in 5s" >> data/mainnet.log
  sleep 5
done
