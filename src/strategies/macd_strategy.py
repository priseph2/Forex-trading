from datetime import datetime, timezone

import pandas as pd

from src.indicators.macd import calculate_macd
from src.signals.models import Direction, Signal
from src.strategies.base import BaseStrategy

_MIN_ROWS = 40  # MACD needs 26+9=35 bars; buffer to 40


class MACDStrategy(BaseStrategy):
    name = "MACD"
    weight = 1.2

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

        macd_df = calculate_macd(ohlcv["Close"])
        macd = macd_df["macd"]
        signal_line = macd_df["signal"]
        histogram = macd_df["histogram"]

        prev_above = macd.iloc[-2] > signal_line.iloc[-2]
        curr_above = macd.iloc[-1] > signal_line.iloc[-1]

        if not prev_above and curr_above:
            direction = Direction.BUY
        elif prev_above and not curr_above:
            direction = Direction.SELL
        else:
            direction = Direction.HOLD

        if direction == Direction.HOLD:
            confidence = 0.5
        else:
            macd_val = abs(float(macd.iloc[-1]))
            hist_val = abs(float(histogram.iloc[-1]))
            raw = hist_val / (macd_val + 1e-10) if macd_val > 0 else 0.5
            confidence = max(0.5, min(1.0, raw))

        return Signal(
            pair=pair,
            strategy=self.name,
            direction=direction,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "macd": round(float(macd.iloc[-1]), 6),
                "signal": round(float(signal_line.iloc[-1]), 6),
                "histogram": round(float(histogram.iloc[-1]), 6),
            },
        )
