from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

Timestamp = datetime
EventSource = Literal["engine", "api"]
EngineEventId = UUID

__all__ = ["EngineEventId", "EventSource", "Timestamp"]
