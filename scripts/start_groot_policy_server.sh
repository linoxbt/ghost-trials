#!/usr/bin/env bash
set -euo pipefail

: "${ISAAC_GROOT_ROOT:?Set ISAAC_GROOT_ROOT to the Isaac-GR00T checkout}"
: "${GR00T_CHECKPOINT:?Set GR00T_CHECKPOINT to a fine-tuned UNITREE_G1_SONIC checkpoint}"
: "${GR00T_CHECKPOINT_DIGEST:?Set GR00T_CHECKPOINT_DIGEST to the inspected content digest}"

GR00T_POLICY_PORT="${GR00T_POLICY_PORT:-5550}"
GR00T_DEVICE="${GR00T_DEVICE:-cuda:0}"
GR00T_POLICY_BIND="${GR00T_POLICY_BIND:-127.0.0.1}"
GHOST_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Validate the actual package before asking the upstream loader to allocate GPU memory.
cd "$GHOST_PROJECT_ROOT"
"$GHOST_PROJECT_ROOT/.venv/bin/python" -m ghost_trials.execution_setup checkpoint "$GR00T_CHECKPOINT" --expected-digest "$GR00T_CHECKPOINT_DIGEST"

cd "$ISAAC_GROOT_ROOT"
exec uv run python gr00t/eval/run_gr00t_server.py \
  --model-path "$GR00T_CHECKPOINT" \
  --embodiment-tag UNITREE_G1_SONIC \
  --device "$GR00T_DEVICE" \
  --host "$GR00T_POLICY_BIND" \
  --port "$GR00T_POLICY_PORT"
