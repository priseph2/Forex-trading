from datetime import datetime, timezone

import pandas as pd

from src.indicators.ema import calculate_ema
from src.signals.models import Direction, Signal
from src.strategies.base import BaseStrategy

_MIN_ROWS = 55  # need EMA50 to be meaningful


class EMACrossoverStrategy(BaseStrategy):
    name = "EMA Crossover"
    weight = 1.5

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

        close = ohlcv["Close"]
        ema20 = calculate_ema(close, 20)
        ema50 = calculate_ema(close, 50)

        prev_above = ema20.iloc[-2] > ema50.iloc[-2]
        curr_above = ema20.iloc[-1] > ema50.iloc[-1]

        if not prev_above and curr_above:
            direction = Direction.BUY
        elif prev_above and not curr_above:
            direction = Direction.SELL
        else:
            direction = Direction.HOLD

        if direction == Direction.HOLD:
            confidence = 0.5
        else:
            # Gap as fraction of price: 0.5% gap → full confidence
            gap = abs(ema20.iloc[-1] - ema50.iloc[-1]) / close.iloc[-1]
            confidence = min(0.5 + (gap / 0.005) * 0.5, 1.0)

        return Signal(
            pair=pair,
            strategy=self.name,
            direction=direction,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "ema20": round(float(ema20.iloc[-1]), 5),
                "ema50": round(float(ema50.iloc[-1]), 5),
            },
        )
