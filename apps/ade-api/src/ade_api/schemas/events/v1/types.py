from __future__ import annotations

from datetime import datetime
from typing import Literal

Timestamp = datetime
EventSource = Literal["api", "engine"]

__all__ = ["EventSource", "Timestamp"]
