#!/usr/bin/env bash
set -euo pipefail

: "${ISAAC_GROOT_ROOT:?Set ISAAC_GROOT_ROOT to the Isaac-GR00T checkout}"
: "${GR00T_DATASET_PATH:?Set GR00T_DATASET_PATH to a processed UNITREE_G1_SONIC LeRobot dataset}"
: "${GR00T_OUTPUT_DIR:?Set GR00T_OUTPUT_DIR for checkpoints}"

NUM_GPUS="${NUM_GPUS:-4}"
GLOBAL_BATCH_SIZE="${GLOBAL_BATCH_SIZE:-32}"
MAX_STEPS="${MAX_STEPS:-20000}"
SAVE_STEPS="${SAVE_STEPS:-5000}"

if [[ ! -d "$GR00T_DATASET_PATH/meta" ]]; then
  echo "Dataset is missing LeRobot metadata: $GR00T_DATASET_PATH/meta" >&2
  exit 1
fi
if [[ "$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)" -lt "$NUM_GPUS" ]]; then
  echo "Fewer than NUM_GPUS=$NUM_GPUS GPUs are visible." >&2
  exit 1
fi

cd "$ISAAC_GROOT_ROOT"
exec uv run python gr00t/experiment/launch_finetune.py \
  --base-model-path nvidia/GR00T-N1.7-3B \
  --dataset-path "$GR00T_DATASET_PATH" \
  --embodiment-tag UNITREE_G1_SONIC \
  --modality-config-path gr00t/configs/data/embodiment_configs.py \
  --num-gpus "$NUM_GPUS" \
  --output-dir "$GR00T_OUTPUT_DIR" \
  --save-total-limit 5 \
  --save-steps "$SAVE_STEPS" \
  --max-steps "$MAX_STEPS" \
  --global-batch-size "$GLOBAL_BATCH_SIZE" \
  --color-jitter-params brightness 0.3 contrast 0.4 saturation 0.5 hue 0.08 \
  --dataloader-num-workers 4
