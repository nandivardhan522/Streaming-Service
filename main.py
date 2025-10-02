'''import asyncio
import logging
from typing import Dict
from fastapi import FastAPI
from config import settings
from inference import TorchModelRunner
from rolling_store import RollingMedianStore
from worker import Worker
from api import create_app
from create_model import InefficientModel
from metrics import Metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stream-service")

# DI container / composition root
event_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.QUEUE_MAXSIZE)
store = RollingMedianStore(window_seconds=settings.WINDOW_SECONDS)
metrics = Metrics(maxlen=settings.METRICS_MAXLEN)

counters: Dict[str, int] = dict(
    total_events=0,
    accepted=0,
    rejected=0,
    scored=0,
)

# Model & runner
model = InefficientModel()
runner = TorchModelRunner(model)

# FastAPI app
app: FastAPI = create_app(
    queue=event_queue,
    store=store,
    counters=counters,
    settings=settings,
    metrics=metrics,
)

# Startup hook spawns workers
@app.on_event("startup")
async def on_startup():
    for i in range(settings.NUM_WORKERS):
        worker = Worker(
            queue=event_queue,
            runner=runner,
            store=store,
            batch_max=settings.BATCH_MAX,
            batch_timeout_ms=settings.BATCH_TIMEOUT_MS,
            counters=counters,
            metrics=metrics,
        )
        asyncio.create_task(worker.run(i))
    logger.info(
        f"Started {settings.NUM_WORKERS} workers; "
        f"window={settings.WINDOW_SECONDS}s, "
        f"batch_max={settings.BATCH_MAX}, "
        f"batch_timeout_ms={settings.BATCH_TIMEOUT_MS}"
    )
'''

import os
import subprocess
import sys
import torch
import asyncio
import logging
import time
from typing import Dict
from fastapi import FastAPI
from config import settings
from inference import TorchModelRunner
from rolling_store import RollingMedianStore
from worker import Worker
from api import create_app
from create_model import InefficientModel
from storage_sqlite import EventStore
from metrics import Metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stream-service")

# DI container / composition root
event_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.QUEUE_MAXSIZE)
rolling = RollingMedianStore(window_seconds=settings.WINDOW_SECONDS)
event_store = EventStore(settings.EVENTS_DB_PATH)
metrics = Metrics(maxlen=settings.METRICS_MAXLEN)

counters: Dict[str, int] = dict(total_events=0, accepted=0, rejected=0, scored=0)

'''
# Model & runner
model = InefficientModel()
runner = TorchModelRunner(model)'''

MODEL_WEIGHTS = "inefficient_model.pth"

def ensure_weights_file():
    if not os.path.exists(MODEL_WEIGHTS):
        # run your script with the current interpreter
        subprocess.run([sys.executable, "create_model.py"], check=True)

def load_model(in_dim=3) -> InefficientModel:
    m = InefficientModel(in_dim)
    state = torch.load(MODEL_WEIGHTS, map_location="cpu")   # loads dict of tensors
    m.load_state_dict(state)                                # attach weights
    m.eval()
    return m

# ---- app startup ----
ensure_weights_file()
model = load_model(3)
runner = TorchModelRunner(model)

# FastAPI app
app: FastAPI = create_app(
    queue=event_queue,
    store=rolling,
    counters=counters,
    settings=settings,
    metrics=metrics,
)

@app.on_event("startup")
async def on_startup():
    # 1) init DB
    await event_store.init()

    # 2) warm in-memory windows from recent persisted events
    now = time.time()
    cutoff = now - settings.WINDOW_SECONDS
    rows = await event_store.load_recent(cutoff)
    for user_id, ts, score in rows:
        await rolling.add(user_id, ts, score, now_s=now)
    logger.info(f"Warmed windows from DB with {len(rows)} recent events.")

    # 3) spawn workers
    for i in range(settings.NUM_WORKERS):
        worker = Worker(
            queue=event_queue,
            runner=runner,
            store=rolling,
            batch_max=settings.BATCH_MAX,
            batch_timeout_ms=settings.BATCH_TIMEOUT_MS,
            counters=counters,
            metrics=metrics,
            event_store=event_store,
        )
        asyncio.create_task(worker.run(i))

    # 4) periodic cleanup to bound DB size
    asyncio.create_task(event_store.periodic_cleanup(settings.RETENTION_SECONDS, interval_seconds=60))

    logger.info(
        f"Started {settings.NUM_WORKERS} workers; window={settings.WINDOW_SECONDS}s, "
        f"batch_max={settings.BATCH_MAX}, batch_timeout_ms={settings.BATCH_TIMEOUT_MS}, "
        f"db={settings.EVENTS_DB_PATH}, retention={settings.RETENTION_SECONDS}s"
    )