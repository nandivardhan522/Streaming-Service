from pydantic import BaseModel
from typing import List

class Event(BaseModel):
    user_id: str
    timestamp: int        # int(time.time())
    features: List[float] # len == 3

class EventBatch(BaseModel):
    events: List[Event]
