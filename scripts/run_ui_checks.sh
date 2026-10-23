#!/bin/sh
# Run the Playwright UI checks against throwaway local servers (synthetic data, no paid calls).
# Usage: scripts/run_ui_checks.sh   (requires `npm ci`, `npm run build:auth`, and `uv sync --extra dev`)
set -eu
root="$(mktemp -d)"
pids=""
# Wait for the servers to exit before deleting their data, and never let cleanup change the result.
cleanup() {
  status=$?
  for pid in $pids; do kill "$pid" 2>/dev/null || true; done
  for pid in $pids; do wait "$pid" 2>/dev/null || true; done
  rm -rf "$root" 2>/dev/null || { sleep 1; rm -rf "$root" 2>/dev/null || true; }
  exit "$status"
}
trap cleanup EXIT INT TERM

serve() { # name port extra-env...
  name="$1"; port="$2"; shift 2
  mkdir -p "$root/$name"
  env GHOST_MODE=local GHOST_SCENARIO_PROVIDER=local GHOST_SIMULATOR_PROVIDER=local GHOST_JUDGE_PROVIDER=local \
    GHOST_PIPELINE_DELAY_SECONDS=0 GHOST_DATA_PATH="$root/$name/state.sqlite3" GHOST_ARTIFACT_ROOT="$root/$name/artifacts" \
    "$@" uv run --frozen uvicorn ghost_trials.app:app --host 127.0.0.1 --port "$port" >"$root/$name.log" 2>&1 &
  pids="$pids $!"
  for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:$port/health" >/dev/null && return 0; sleep 1; done
  cat "$root/$name.log" >&2; return 1
}
private() { # token-authenticated isolated server expected by evidence/physical checks
  serve "$1" "$2" GHOST_ADMIN_TOKEN="$(printf 'a%.0s' $(seq 48))" GHOST_OPERATOR_TOKEN="$(printf 'o%.0s' $(seq 48))" \
    GHOST_VIEWER_TOKEN="$(printf 'v%.0s' $(seq 48))" GHOST_ALLOWED_ORIGINS="http://127.0.0.1:$2" GHOST_COOKIE_SECURE=false
}

# A synthetic orange clip, never robot footage, for the physical-recording upload flow.
export GHOST_FIXTURE_VIDEO="$root/fixture-not-hardware.mp4"
ffmpeg -v error -f lavfi -i color=c=orange:s=64x64:r=20 -t 1.2 -c:v libx264 -pix_fmt yuv420p "$GHOST_FIXTURE_VIDEO"

serve open 8010 GHOST_UNAUTHENTICATED_LOCAL_DEV=true
private evidence 8013
private physical 8012
export GHOST_PREVIEW_URL=http://127.0.0.1:8010
# Order matters: check_frontend seeds the trials that check_evaluation compares.
for check in check_frontend check_evaluation check_public_site check_agent_frontend check_team check_traction \
             check_evidence_frontend check_physical_frontend; do
  echo "== $check"
  node "scripts/$check.cjs"
done
# check_auth needs a real Privy app configuration; run it manually against a configured deployment.
echo "UI checks passed"
