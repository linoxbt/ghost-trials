ARG ARENA_IMAGE
FROM ${ARENA_IMAGE}
WORKDIR /app
COPY pyproject.toml README.md ./
COPY ghost_trials ./ghost_trials
COPY workers ./workers
COPY scripts ./scripts
RUN chmod +x /app/scripts/*.sh
RUN python -m pip install --no-cache-dir '.[worker]'
ENV ISAAC_WORKER_OUTPUT_ROOT=/data/ghost-trials
VOLUME ["/data/ghost-trials"]
EXPOSE 9000
CMD ["python", "-m", "uvicorn", "workers.isaac.service:app", "--host", "0.0.0.0", "--port", "9000"]
