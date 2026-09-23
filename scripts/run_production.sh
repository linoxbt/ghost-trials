#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${GHOST_ENV_FILE:-$ROOT_DIR/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; copy deployment/production.env.example and fill it." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

cd "$ROOT_DIR"
uv run ghost-trials-preflight
exec uv run uvicorn ghost_trials.app:app \
  --host "${GHOST_BIND_ADDRESS:-0.0.0.0}" \
  --port "${GHOST_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips "${GHOST_FORWARDED_ALLOW_IPS:-127.0.0.1}"
