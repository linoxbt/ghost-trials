#!/usr/bin/env bash
set -euo pipefail

CHECKPOINT="${1:?Usage: $0 /path/to/checkpoint}"
if [[ ! -d "$CHECKPOINT" ]]; then
  echo "Checkpoint directory not found: $CHECKPOINT" >&2
  exit 1
fi

cd "$CHECKPOINT"
find . -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  | sha256sum \
  | awk '{print "sha256:" $1}'
