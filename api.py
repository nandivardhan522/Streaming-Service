from fastapi import FastAPI
from typing import Dict
import asyncio
from domain import EventBatch
from rolling_store import RollingMedianStore
from metrics import Metrics

def create_app(
    *,
    queue: asyncio.Queue,
    store: RollingMedianStore,
    counters: Dict[str, int],
    settings,
    metrics: Metrics,
) -> FastAPI:
    app = FastAPI()

    @app.post("/ingest")
    async def ingest(batch: EventBatch):
        counters["total_events"] += len(batch.events)
        for ev in batch.events:
            try:
                queue.put_nowait(ev)
                counters["accepted"] += 1
            except asyncio.QueueFull:
                counters["rejected"] += 1
        return {
            "message": "ok",
            "accepted": counters["accepted"],
            "rejected": counters["rejected"],
            "queue_size": queue.qsize(),
        }

    @app.get("/stats")
    async def stats():
        mom = await store.median_of_medians() 
        return {
            "queue_size": queue.qsize(),
            "total_events": counters["total_events"],
            "accepted": counters["accepted"],
            "rejected": counters["rejected"],
            "number_of_users": store.user_count(),
            "scored": counters["scored"],
            "window_seconds": settings.WINDOW_SECONDS,
            "median_of_medians": mom,
            "latency": metrics.snapshot(),  # ← NEW
        }

    @app.get("/users/{user_id}/median")
    async def get_user_median(user_id: str):
        m = await store.median(user_id)
        return {"user_id": user_id, "median": m, "window_seconds": settings.WINDOW_SECONDS}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "queue_size": queue.qsize()}

    return app
