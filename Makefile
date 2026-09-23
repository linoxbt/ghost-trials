.PHONY: dev mobile test preflight production

dev:
	uv run uvicorn ghost_trials.app:app --reload --host 0.0.0.0 --port 8000

mobile: dev

test:
	uv run --extra dev pytest

preflight:
	uv run ghost-trials-preflight

production:
	bash scripts/run_production.sh
