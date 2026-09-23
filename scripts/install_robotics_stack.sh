#!/usr/bin/env bash
set -euo pipefail

: "${HF_TOKEN:?Set a Hugging Face read token after accepting gated model terms}"
ROBOTICS_ROOT="${ROBOTICS_ROOT:-/opt/robotics}"
# Source interfaces inspected on 2026-09-13; GPU compatibility still needs validation.
GROOT_REF="${GROOT_REF:-51d4c89f72fda44cbf77285c6a8114b52676b8a1}"
SONIC_REF="${SONIC_REF:-087f9ac01d46f6d8e4d0b73c01ae64799f292a38}"

mkdir -p "$ROBOTICS_ROOT"
if [[ ! -d "$ROBOTICS_ROOT/Isaac-GR00T/.git" ]]; then
  git clone https://github.com/NVIDIA/Isaac-GR00T.git "$ROBOTICS_ROOT/Isaac-GR00T"
fi
if [[ ! -d "$ROBOTICS_ROOT/GR00T-WholeBodyControl/.git" ]]; then
  git clone https://github.com/NVlabs/GR00T-WholeBodyControl.git "$ROBOTICS_ROOT/GR00T-WholeBodyControl"
fi

git -C "$ROBOTICS_ROOT/Isaac-GR00T" fetch --tags origin
git -C "$ROBOTICS_ROOT/Isaac-GR00T" checkout "$GROOT_REF"
git -C "$ROBOTICS_ROOT/GR00T-WholeBodyControl" fetch --tags origin
git -C "$ROBOTICS_ROOT/GR00T-WholeBodyControl" checkout "$SONIC_REF"
git -C "$ROBOTICS_ROOT/GR00T-WholeBodyControl" lfs pull --include='gear_sonic/data/robot_model/**,gear_sonic_deploy/**'

cd "$ROBOTICS_ROOT/Isaac-GR00T"
uv sync --all-extras

cd "$ROBOTICS_ROOT/GR00T-WholeBodyControl"
uv run --no-project --with huggingface_hub python download_from_hf.py --sonic-v1-1
if [[ ! -d .venv_inference ]]; then
  bash install_scripts/install_inference.sh
fi
if [[ ! -d .venv_sim ]]; then
  bash install_scripts/install_mujoco_sim.sh
fi
uv pip install --python .venv_sim/bin/python 'imageio[ffmpeg]>=2.37,<3'

git -C "$ROBOTICS_ROOT/Isaac-GR00T" rev-parse HEAD
git -C "$ROBOTICS_ROOT/GR00T-WholeBodyControl" rev-parse HEAD
echo "Python environments and public SONIC assets installed. Build the C++ decoder using TensorRT 10.13 before trials."
