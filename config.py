'''import os

class Settings:
    def __init__(self) -> None:
        self.QUEUE_MAXSIZE     = int(os.getenv("QUEUE_MAXSIZE", "200000"))
        self.NUM_WORKERS       = int(os.getenv("NUM_WORKERS", "4"))
        self.BATCH_MAX         = int(os.getenv("BATCH_MAX", "512"))
        self.BATCH_TIMEOUT_MS  = int(os.getenv("BATCH_TIMEOUT_MS", "2"))
        self.WINDOW_SECONDS    = int(os.getenv("WINDOW_SECONDS", "300"))  # 5 min
        self.METRICS_MAXLEN    = int(os.getenv("METRICS_MAXLEN", "2048")) # samples kept per metric

settings = Settings()'''

import os

class Settings:
    def __init__(self) -> None:
        self.QUEUE_MAXSIZE     = int(os.getenv("QUEUE_MAXSIZE", "200000"))
        self.NUM_WORKERS       = int(os.getenv("NUM_WORKERS", "4"))
        self.BATCH_MAX         = int(os.getenv("BATCH_MAX", "512"))
        self.BATCH_TIMEOUT_MS  = int(os.getenv("BATCH_TIMEOUT_MS", "2"))
        self.WINDOW_SECONDS    = int(os.getenv("WINDOW_SECONDS", "300"))   # 5 min
        self.METRICS_MAXLEN    = int(os.getenv("METRICS_MAXLEN", "2048")) # if you added metrics
        self.EVENTS_DB_PATH    = os.getenv("EVENTS_DB_PATH", "events.db")
        self.RETENTION_SECONDS = int(os.getenv("RETENTION_SECONDS", "3600"))  # keep 1h by default

settings = Settings()

