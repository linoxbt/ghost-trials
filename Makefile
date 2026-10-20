.PHONY: dev mobile test preflight production

dev:
	uv run uvicorn ghost_trials.app:app --reload --host 127.0.0.1 --port 8000

mobile:
	uv run python -m scripts.run_cpu --host 0.0.0.0 --port 8000

test:
	uv run --extra dev pytest

preflight:
	uv run ghost-trials-preflight

production:
	bash scripts/run_production.sh
