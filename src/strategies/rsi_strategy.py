from datetime import datetime, timezone

import pandas as pd

from src.indicators.rsi import calculate_rsi
from src.signals.models import Direction, Signal
from src.strategies.base import BaseStrategy

_MIN_ROWS = 20


class RSIStrategy(BaseStrategy):
    name = "RSI"
    weight = 1.0
    overbought: float = 70.0
    oversold: float = 30.0

    def generate(self, pair: str, ohlcv: pd.DataFrame) -> Signal:
        if len(ohlcv) < _MIN_ROWS:
            return Signal(
                pair=pair,
                strategy=self.name,
                direction=Direction.HOLD,
                confidence=0.5,
                timestamp=datetime.now(timezone.utc),
                metadata={"reason": "insufficient_data"},
            )

        rsi = calculate_rsi(ohlcv["Close"])
        latest = float(rsi.iloc[-1])

        if latest < self.oversold:
            direction = Direction.BUY
            confidence = (self.oversold - latest) / self.oversold
        elif latest > self.overbought:
            direction = Direction.SELL
            confidence = (latest - self.overbought) / (100.0 - self.overbought)
        else:
            direction = Direction.HOLD
            confidence = 0.5

        return Signal(
            pair=pair,
            strategy=self.name,
            direction=direction,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={"rsi": round(latest, 2)},
        )
