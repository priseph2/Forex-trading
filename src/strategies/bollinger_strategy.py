from datetime import datetime, timezone

import pandas as pd

from src.indicators.bollinger import calculate_bollinger_bands
from src.signals.models import Direction, Signal
from src.strategies.base import BaseStrategy

_MIN_ROWS = 25


class BollingerStrategy(BaseStrategy):
    name = "Bollinger Bands"
    weight = 1.0

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
        bands = calculate_bollinger_bands(close)
        upper = float(bands["upper"].iloc[-1])
        lower = float(bands["lower"].iloc[-1])
        price = float(close.iloc[-1])

        if pd.isna(upper) or pd.isna(lower):
            return Signal(
                pair=pair,
                strategy=self.name,
                direction=Direction.HOLD,
                confidence=0.5,
                timestamp=datetime.now(timezone.utc),
                metadata={"reason": "insufficient_data"},
            )

        band_width = upper - lower

        if price < lower:
            direction = Direction.BUY
            confidence = min((lower - price) / (band_width + 1e-10), 1.0)
        elif price > upper:
            direction = Direction.SELL
            confidence = min((price - upper) / (band_width + 1e-10), 1.0)
        else:
            direction = Direction.HOLD
            confidence = 0.5

        return Signal(
            pair=pair,
            strategy=self.name,
            direction=direction,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "price": round(price, 5),
                "upper": round(upper, 5),
                "lower": round(lower, 5),
            },
        )
