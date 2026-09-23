FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY ghost_trials ./ghost_trials
COPY static ./static
RUN pip install --no-cache-dir .
ENV GHOST_DATA_PATH=/data/state.json
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "ghost_trials.app:app", "--host", "0.0.0.0", "--port", "8000"]
