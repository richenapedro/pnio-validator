from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReadRequest:
    """Represents an acyclic PNIO CM Read Implicit request."""
    device_name: str
    slot: int
    subslot: int
    index: int
    length: int
    block_version: int = 1


@dataclass(frozen=True)
class ReadResult:
    """Normalized read outcome independent from the underlying transport."""
    ok: bool
    data: bytes
    latency_ms: float
    error: Optional[str] = None