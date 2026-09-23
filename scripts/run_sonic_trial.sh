#!/usr/bin/env bash
set -euo pipefail
: "${GEAR_SONIC_ROOT:?Set GEAR_SONIC_ROOT to the pinned SONIC checkout}"
GHOST_SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$GHOST_SOURCE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$GEAR_SONIC_ROOT/.venv_sim/bin/python" -m workers.isaac.sonic_trial \
  --sonic-root "$GEAR_SONIC_ROOT" "$@"
