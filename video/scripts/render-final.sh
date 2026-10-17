#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm run draft
npm run render
node scripts/final.mjs
npm run poster
if [[ "${FINAL_4K:-}" == "1" ]]; then
  npm run render4k
else
  echo "4K skipped"
fi
