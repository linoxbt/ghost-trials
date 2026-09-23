#!/usr/bin/env bash
set -euo pipefail
: "${ISAAC_ARENA_ROOT:?Set ISAAC_ARENA_ROOT to the pinned Arena checkout}"
: "${ISAAC_ARENA_PYTHON:?Set ISAAC_ARENA_PYTHON to the Python executable in the installed Arena environment}"
GHOST_SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$GHOST_SOURCE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ISAAC_ARENA_ROOT"
exec "$ISAAC_ARENA_PYTHON" -m workers.isaac.arena_trial \
  --policy-config isaaclab_arena_gr00t/policy/config/g1_locomanip_gr00t_closedloop_config.yaml "$@"
