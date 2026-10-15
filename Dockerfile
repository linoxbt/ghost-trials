FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS auth-ui
WORKDIR /ui
COPY package.json package-lock.json ./
COPY frontend ./frontend
COPY scripts/build_auth.mjs ./scripts/build_auth.mjs
# Keep dependency installation and removal in one layer: only built assets remain.
RUN npm ci --no-audit --no-fund && npm run build:auth && npm cache clean --force && rm -rf /ui/node_modules

FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
WORKDIR /app
COPY pyproject.toml README.md uv.lock ./
RUN pip install --no-cache-dir uv==0.11.21 && uv sync --frozen --no-dev --extra storage --no-install-project
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY ghost_trials ./ghost_trials
COPY workers ./workers
COPY static ./static
COPY --from=auth-ui /ui/static/auth ./static/auth
COPY deployment/logging.json ./deployment/logging.json
COPY deployment/start-api.sh ./deployment/start-api.sh
RUN uv sync --frozen --no-dev --extra storage
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV GHOST_DATA_PATH=/data/state.json
ENV GHOST_ARTIFACT_ROOT=/data/artifacts
RUN install -d -m 0700 -o 10001 -g 10001 /data
RUN chmod 0755 /app/deployment/start-api.sh
USER 10001:10001
EXPOSE 8000
CMD ["/app/deployment/start-api.sh"]
