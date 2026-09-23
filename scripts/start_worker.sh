#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_ENV="${GHOST_WORKER_ENV_FILE:-$ROOT_DIR/deployment/private/worker.env}"
if [[ ! -f "$WORKER_ENV" ]]; then
  echo "Prepare worker credentials first: .venv/bin/python -m ghost_trials.execution_setup prepare" >&2
  exit 1
fi
set -a
source "$WORKER_ENV"
set +a
: "${ISAAC_WORKER_TOKEN:?Worker authentication is required}"
cd "$ROOT_DIR"
exec "$ROOT_DIR/.venv/bin/uvicorn" workers.isaac.service:app \
  --host "${GHOST_WORKER_BIND:-127.0.0.1}" --port "${GHOST_WORKER_PORT:-9000}"
