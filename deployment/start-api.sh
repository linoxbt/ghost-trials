#!/bin/sh
set -eu

# Railway persistent volumes are initially root-owned. Its RAILWAY_RUN_UID=0
# setting lets this entrypoint assign only the dedicated /data mount, then drop
# privileges before the API starts. Ordinary Docker runs stay non-root.
if [ "$(id -u)" = 0 ]; then
  chown 10001:10001 /data
  for path in /data/state.json /data/state.sqlite3 /data/state.sqlite3-wal /data/state.sqlite3-shm /data/artifacts; do
    if [ -e "$path" ]; then chown 10001:10001 "$path"; fi
  done
  exec setpriv --reuid=10001 --regid=10001 --clear-groups \
    uvicorn ghost_trials.app:app --host 0.0.0.0 --port "${PORT:-8000}"
fi

exec uvicorn ghost_trials.app:app --host 0.0.0.0 --port "${PORT:-8000}"
