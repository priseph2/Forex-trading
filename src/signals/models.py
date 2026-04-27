from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    pair: str
    strategy: str
    direction: Direction
    confidence: float  # 0.0 – 1.0
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PairResult:
    pair: str
    timestamp: datetime
    signals: list[Signal]
    combined: Direction
    combined_confidence: float  # 0.0 – 1.0
