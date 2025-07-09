from dataclasses import dataclass
from typing import Any


@dataclass
class CacheItem:
    value: Any
    expire_at: float | None
