import aiosqlite
import asyncio
import time
from typing import List, Tuple, Optional

class EventStore:
    def __init__(self, path: str = "events.db") -> None:
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA synchronous=NORMAL;")
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events(
                user_id TEXT NOT NULL,
                ts REAL NOT NULL,
                score REAL NOT NULL
            )
        """)
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, ts)")
        await self._db.commit()

    async def save_event(self, user_id: str, ts: float, score: float) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO events(user_id, ts, score) VALUES (?, ?, ?)",
            (user_id, ts, score),
        )
        await self._db.commit()  # simple & safe; you can batch for higher throughput

    async def load_recent(self, cutoff_ts: float) -> List[Tuple[str, float, float]]:
        """Return (user_id, ts, score) for rows with ts >= cutoff_ts."""
        assert self._db is not None
        rows: List[Tuple[str, float, float]] = []
        async with self._db.execute(
            "SELECT user_id, ts, score FROM events WHERE ts >= ? ORDER BY ts ASC",
            (cutoff_ts,),
        ) as cur:
            async for r in cur:
                rows.append((r[0], float(r[1]), float(r[2])))
        return rows

    async def delete_older_than(self, cutoff_ts: float) -> int:
        """Delete rows strictly older than cutoff; return number deleted."""
        assert self._db is not None
        cur = await self._db.execute("DELETE FROM events WHERE ts < ?", (cutoff_ts,))
        await self._db.commit()
        return cur.rowcount or 0

    async def periodic_cleanup(self, retention_seconds: int, interval_seconds: int = 60) -> None:
        """Background task: keep DB bounded by retention."""
        assert retention_seconds > 0
        while True:
            try:
                now = time.time()
                cutoff = now - retention_seconds
                await self.delete_older_than(cutoff)
            except Exception:
                # swallow and continue; don't crash the task
                pass
            await asyncio.sleep(interval_seconds)
