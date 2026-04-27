from abc import ABC, abstractmethod

import pandas as pd

from src.signals.models import Signal


class BaseStrategy(ABC):
    name: str = "Base"
    weight: float = 1.0

    @abstractmethod
    def generate(self, pair: str, ohlcv: pd.DataFrame) -> Signal:
        """Generate a Signal for the given pair from its OHLCV DataFrame."""
