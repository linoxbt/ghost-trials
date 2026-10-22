.PHONY: dev mobile test preflight production

dev:
	uv run python -m scripts.run_cpu --host 127.0.0.1 --port 8000

# LAN access is a public bind: it needs individual sign-in configured in .env (see README).
mobile:
	GHOST_PUBLIC_DEPLOYMENT=true uv run python -m scripts.run_cpu --host 0.0.0.0 --port 8000

test:
	uv run --extra dev pytest

preflight:
	uv run ghost-trials-preflight

production:
	bash scripts/run_production.sh
