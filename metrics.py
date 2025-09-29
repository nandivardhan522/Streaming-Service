from collections import deque
from typing import Dict, Any, List

class LatencyMetric:
    """
    Lightweight latency tracker with a fixed-size window for quantiles.
    Not process-safe (per-Uvicorn worker only), but asyncio-task safe enough.
    """
    def __init__(self, name: str, maxlen: int = 2048) -> None:
        self.name = name
        self.values = deque(maxlen=maxlen)
        self.count = 0
        self.sum_ms = 0.0
        self.min_ms = float("inf")
        self.max_ms = 0.0

    def observe(self, ms: float) -> None:
        if ms < 0:
            ms = 0.0
        self.values.append(ms)
        self.count += 1
        self.sum_ms += ms
        if ms < self.min_ms:
            self.min_ms = ms
        if ms > self.max_ms:
            self.max_ms = ms

    def _quantile(self, sorted_vals: List[float], q: float) -> float:
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        idx = min(max(int(q * (n - 1)), 0), n - 1)
        return sorted_vals[idx]

    def snapshot(self) -> Dict[str, Any]:
        vals = list(self.values)
        n = len(vals)
        avg = (self.sum_ms / self.count) if self.count else 0.0
        if n:
            s = sorted(vals)
            return {
                "count": self.count,
                "window_size": n,
                "avg_ms": avg,
                "min_ms": self.min_ms,
                "max_ms": self.max_ms,
                "p50_ms": self._quantile(s, 0.50),
                "p90_ms": self._quantile(s, 0.90),
                "p95_ms": self._quantile(s, 0.95),
                "p99_ms": self._quantile(s, 0.99),
            }
        return {
            "count": self.count,
            "window_size": 0,
            "avg_ms": avg,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
        }


class Metrics:
    """
    Group of latency metrics we care about.
    - batch_build_ms: time from first dequeued item until batch ready for inference
    - inference_ms: forward pass latency per batch
    - store_add_ms: per-event time to update the rolling store
    - event_age_ms: (processing_now - event.timestamp) per event
    """
    def __init__(self, maxlen: int = 2048) -> None:
        self.batch_build_ms = LatencyMetric("batch_build_ms", maxlen=maxlen)
        self.inference_ms = LatencyMetric("inference_ms", maxlen=maxlen)
        self.store_add_ms = LatencyMetric("store_add_ms", maxlen=maxlen)
        self.event_age_ms = LatencyMetric("event_age_ms", maxlen=maxlen)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "batch_build_ms": self.batch_build_ms.snapshot(),
            "inference_ms": self.inference_ms.snapshot(),
            "store_add_ms": self.store_add_ms.snapshot(),
            "event_age_ms": self.event_age_ms.snapshot(),
        }
