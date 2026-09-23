#!/usr/bin/env bash
set -euo pipefail

: "${GEAR_SONIC_ROOT:?Set GEAR_SONIC_ROOT to the GR00T-WholeBodyControl checkout}"
: "${GR00T_CHECKPOINT:?Set GR00T_CHECKPOINT to a fine-tuned UNITREE_G1_SONIC checkpoint}"

GR00T_POLICY_HOST="${GR00T_POLICY_HOST:-127.0.0.1}"
GR00T_POLICY_PORT="${GR00T_POLICY_PORT:-5550}"
GHOST_TASK_PROMPT="${GHOST_TASK_PROMPT:-walk through the warehouse and avoid hazards}"

cd "$GEAR_SONIC_ROOT"
exec .venv_inference/bin/python gear_sonic/scripts/launch_inference.py \
  --sim \
  --deploy-checkpoint policy/sonic_v1_1/model \
  --deploy-obs-config policy/sonic_v1_1/observation_config.yaml \
  --deploy-motor-kp-scale 4,10=1.5 \
  --deploy-motor-kd-scale 4,10=1.5 \
  --policy-host "$GR00T_POLICY_HOST" \
  --policy-port "$GR00T_POLICY_PORT" \
  --prompt "$GHOST_TASK_PROMPT" \
  --no-data-exporter
