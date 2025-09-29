import time
import asyncio
from typing import Optional, Tuple, List, Dict
from bisect import bisect_left, insort
from collections import defaultdict

class UserWindow:
    __slots__ = ("lock", "samples_by_ts", "scores_sorted")
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.samples_by_ts: List[Tuple[float, float]] = []  # (ts, score), sorted by ts
        self.scores_sorted: List[float] = []                # sorted ascending

class RollingMedianStore:
    """
    Per-user rolling median over a time window (event-time; robust to out-of-order arrivals).
    """
    def __init__(self, window_seconds: int) -> None:
        self.window_seconds = window_seconds
        self._users: Dict[str, UserWindow] = defaultdict(UserWindow)

    async def add(self, user_id: str, ts_s: float, score: float, *, now_s: Optional[float] = None) -> None:
        if now_s is None:
            now_s = time.time()
        uw = self._users[user_id]
        async with uw.lock:
            cutoff = now_s - self.window_seconds
            while uw.samples_by_ts and uw.samples_by_ts[0][0] < cutoff:
                _, old_score = uw.samples_by_ts.pop(0)
                idx = bisect_left(uw.scores_sorted, old_score)
                if 0 <= idx < len(uw.scores_sorted) and uw.scores_sorted[idx] == old_score:
                    uw.scores_sorted.pop(idx)

            insort(uw.samples_by_ts, (ts_s, score))
            insort(uw.scores_sorted, score)

    async def median(self, user_id: str, *, now_s: Optional[float] = None) -> Optional[float]:
        if now_s is None:
            now_s = time.time()
        uw = self._users.get(user_id)
        if not uw:
            return None
        async with uw.lock:
            cutoff = now_s - self.window_seconds
            while uw.samples_by_ts and uw.samples_by_ts[0][0] < cutoff:
                _, old_score = uw.samples_by_ts.pop(0)
                idx = bisect_left(uw.scores_sorted, old_score)
                if 0 <= idx < len(uw.scores_sorted) and uw.scores_sorted[idx] == old_score:
                    uw.scores_sorted.pop(idx)

            n = len(uw.scores_sorted)
            if n == 0:
                return None
            mid = n // 2
            return uw.scores_sorted[mid] if n % 2 else 0.5 * (uw.scores_sorted[mid-1] + uw.scores_sorted[mid])

    async def median_of_medians(self, *, now_s: Optional[float] = None) -> Optional[float]:
        """
        Compute the median across all users' current window medians.
        Only users with at least one sample in-window are included.
        """
        if now_s is None:
            now_s = time.time()

        # Copy keys so we don't hold a reference that can change during iteration
        user_ids = list(self._users.keys())
        medians: List[float] = []

        for uid in user_ids:
            m = await self.median(uid, now_s=now_s)  # safe: acquires per-user lock internally
            if m is not None:
                medians.append(m)

        if not medians:
            return None

        medians.sort()
        n = len(medians)
        mid = n // 2
        return medians[mid] if n % 2 else 0.5 * (medians[mid - 1] + medians[mid])


    def user_count(self) -> int:
        return len(self._users)

    def user_ids(self) -> List[str]:
        return list(self._users.keys())
