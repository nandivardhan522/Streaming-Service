# Streaming Service

A FastAPI-based streaming inference service that ingests user events, performs batched model inference (PyTorch), maintains per-user rolling medians over a time window, and exposes operational metrics.

## Prerequisites
- Python 3.13 (project venv included under `venv/`)
- macOS or Linux recommended

## Quick start (Docker)
```bash
# 1) Download the repository ZIP from GitHub and unzip it
#    Alternatively: git clone <repo-url>

# 2) In the project directory, build the Docker image
docker build -t streaming-service .

# 3) Run the container mapping host port 8000 to container port 8000
docker run --rm -p 8000:8000 streaming-service

# 4) Verify the server is running
curl http://localhost:8000/health
# API docs: http://localhost:8000/docs
```

## Configuration
Environment variables (defaults in `config.py`):
- `QUEUE_MAXSIZE` (default 200000)
- `NUM_WORKERS` (default 4)
- `BATCH_MAX` (default 512)
- `BATCH_TIMEOUT_MS` (default 2)
- `WINDOW_SECONDS` (default 300)
- `METRICS_MAXLEN` (default 2048)

## API
- `POST /ingest` — Ingest a batch of events
  - Body:
    ```json
    {
      "events": [
        {"user_id": "user-1", "timestamp": 1720000000, "features": [0.1, 0.2, 0.3]}
      ]
    }
    ```
  - Returns accepted/rejected counts and queue size.

- `GET /stats` — Service stats
  - Returns queue/counter values, current median-of-medians, and latency metrics snapshot.

- `GET /users/{user_id}/median` — Median for a given user within the rolling window.

- `GET /health` — Simple health check.

## Architecture overview
- `main.py` — Composition root. Creates shared `asyncio.Queue`, `RollingMedianStore`, `Metrics`, loads `InefficientModel` and wraps with `TorchModelRunner`, builds FastAPI app via `create_app`, and spawns `Worker`s on startup.
- `api.py` — Defines FastAPI routes for ingesting events and querying stats.
- `worker.py` — Async worker that batches items from the queue, performs model inference via `InferenceRunner`, updates `RollingMedianStore`, and tracks latencies in `Metrics`.
- `rolling_store.py` — In-memory per-user rolling window and medians, plus median-of-medians.
- `metrics.py` — Lightweight latency metrics with snapshots (avg, min, max, p50/p90/p95/p99).
- `inference.py` — `TorchModelRunner` that runs a PyTorch model for batch predictions.
- `create_model.py` — Utility to create and save a small example model (`inefficient_model.pt`).
- `event_generator.py` — High-throughput load generator posting events to `/ingest`.
- `storage_sqlite.py` — Async SQLite persistence (optional helper) for events using `aiosqlite`.
- `config.py` — Reads environment variables into `settings`.

## Running the load generator
With the server running on port 8000:
```bash
python event_generator.py
# or customize RPS/duration/users by editing the script defaults
```

## Development tips
- Activate the venv for all commands:
  ```bash
  source ./venv/bin/activate
  ```
- If you change dependencies, add them to your venv:
  ```bash
  python -m pip install <package>
  ```
- Common troubleshooting:
  - If `aiosqlite` is missing: `python -m pip install "aiosqlite<1.0.0"`
  - If imports fail, ensure you are using the project venv Python.

## License
MIT (or your preferred license).
