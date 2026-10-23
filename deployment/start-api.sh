#!/bin/sh
set -eu

# A container listening publicly must fail closed unless individual auth and
# exact HTTPS origins are configured. Local developers may explicitly opt out.
export GHOST_PUBLIC_DEPLOYMENT="${GHOST_PUBLIC_DEPLOYMENT:-true}"

# Railway persistent volumes are initially root-owned. Its RAILWAY_RUN_UID=0
# setting lets this entrypoint assign only the dedicated /data mount, then drop
# privileges before the API starts. The API process always runs as UID 10001.
if [ "$(id -u)" = 0 ]; then
  chown 10001:10001 /data
  for path in /data/state.json /data/state.sqlite3 /data/state.sqlite3-wal /data/state.sqlite3-shm; do
    if [ -e "$path" ]; then chown 10001:10001 "$path"; fi
  done
  # Evidence written by an earlier root process must stay readable and writable by the API user.
  if [ -d /data/artifacts ]; then chown -R 10001:10001 /data/artifacts; fi
  exec setpriv --reuid=10001 --regid=10001 --clear-groups \
    uvicorn ghost_trials.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-server-header --log-config /app/deployment/logging.json
fi

# One worker only: SQLite state is guarded by a single-process lease.
exec uvicorn ghost_trials.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-server-header --log-config /app/deployment/logging.json
