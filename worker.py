'''import asyncio
import time
import logging
from typing import List
from domain import Event
from inference import InferenceRunner
from rolling_store import RollingMedianStore
from metrics import Metrics

logger = logging.getLogger("stream-service")

class Worker:
    def __init__(
        self,
        *,
        queue: asyncio.Queue,
        runner: InferenceRunner,
        store: RollingMedianStore,
        batch_max: int,
        batch_timeout_ms: int,
        counters: dict,
        metrics: Metrics,
    ) -> None:
        self.queue = queue
        self.runner = runner
        self.store = store
        self.batch_max = batch_max
        self.batch_timeout_ms = batch_timeout_ms
        self.counters = counters
        self.metrics = metrics

    async def run(self, worker_id: int) -> None:
        while True:
            batch: List[Event] = []
            try:
                # First dequeue
                t_first_get_start = time.perf_counter()
                first = await self.queue.get()
                batch = [first]
                t_first_get_end = time.perf_counter()

                # Build batch (drain queue up to constraints)
                t_batch_build_start = t_first_get_end
                while len(batch) < self.batch_max:
                    remaining = self.batch_timeout_ms / 1000.0 - (time.perf_counter() - t_first_get_end)
                    if remaining <= 0:
                        break
                    try:
                        ev = await asyncio.wait_for(self.queue.get(), timeout=remaining)
                        batch.append(ev)
                    except asyncio.TimeoutError:
                        break
                t_batch_build_end = time.perf_counter()
                self.metrics.batch_build_ms.observe((t_batch_build_end - t_batch_build_start) * 1000.0)

                # Inference
                features = [e.features for e in batch]
                t_inf_start = time.perf_counter()
                scores = self.runner.predict_batch(features)
                t_inf_end = time.perf_counter()
                self.metrics.inference_ms.observe((t_inf_end - t_inf_start) * 1000.0)

                # Update store + per-event age
                now_s = time.time()
                for ev, score in zip(batch, scores):
                    # event age relative to processing time
                    self.metrics.event_age_ms.observe((now_s - float(ev.timestamp)) * 1000.0)

                    t_add_start = time.perf_counter()
                    await self.store.add(ev.user_id, float(ev.timestamp), float(score), now_s=now_s)
                    t_add_end = time.perf_counter()
                    self.metrics.store_add_ms.observe((t_add_end - t_add_start) * 1000.0)

                    self.counters["scored"] += 1

            except Exception as e:
                logger.exception(f"[worker {worker_id}] error: {e}")
            finally:
                for _ in batch:
                    self.queue.task_done()'''

import asyncio
import time
import logging
from typing import List, Optional
from domain import Event
from inference import InferenceRunner
from rolling_store import RollingMedianStore
from metrics import Metrics
from storage_sqlite import EventStore

logger = logging.getLogger("stream-service")

class Worker:
    def __init__(
        self,
        *,
        queue: asyncio.Queue,
        runner: InferenceRunner,
        store: RollingMedianStore,
        batch_max: int,
        batch_timeout_ms: int,
        counters: dict,
        metrics: Optional[Metrics],
        event_store: EventStore,
    ) -> None:
        self.queue = queue
        self.runner = runner
        self.store = store
        self.batch_max = batch_max
        self.batch_timeout_ms = batch_timeout_ms
        self.counters = counters
        self.metrics = metrics
        self.event_store = event_store

    async def run(self, worker_id: int) -> None:
        while True:
            batch: List[Event] = []
            try:
                # First dequeue
                t_first_get_end = time.perf_counter()
                first = await self.queue.get()
                batch = [first]

                # Build batch (drain queue up to constraints)
                t_batch_build_start = t_first_get_end
                while len(batch) < self.batch_max:
                    remaining = self.batch_timeout_ms / 1000.0 - (time.perf_counter() - t_first_get_end)
                    if remaining <= 0:
                        break
                    try:
                        ev = await asyncio.wait_for(self.queue.get(), timeout=remaining)
                        batch.append(ev)
                    except asyncio.TimeoutError:
                        break
                t_batch_build_end = time.perf_counter()
                if self.metrics:
                    self.metrics.batch_build_ms.observe((t_batch_build_end - t_batch_build_start) * 1000.0)

                # Inference
                features = [e.features for e in batch]
                t_inf_start = time.perf_counter()
                scores = self.runner.predict_batch(features)
                t_inf_end = time.perf_counter()
                if self.metrics:
                    self.metrics.inference_ms.observe((t_inf_end - t_inf_start) * 1000.0)

                # Update store + persist + per-event age
                now_s = time.time()
                for ev, score in zip(batch, scores):
                    if self.metrics:
                        self.metrics.event_age_ms.observe((now_s - float(ev.timestamp)) * 1000.0)

                    t_add_start = time.perf_counter()
                    await self.store.add(ev.user_id, float(ev.timestamp), float(score), now_s=now_s)
                    t_add_end = time.perf_counter()
                    if self.metrics:
                        self.metrics.store_add_ms.observe((t_add_end - t_add_start) * 1000.0)

                    await self.event_store.save_event(ev.user_id, float(ev.timestamp), float(score))
                    self.counters["scored"] += 1

            except Exception as e:
                logger.exception(f"[worker {worker_id}] error: {e}")
            finally:
                for _ in batch:
                    self.queue.task_done()