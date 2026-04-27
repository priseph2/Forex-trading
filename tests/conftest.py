from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest


def _make_ohlcv(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    dates = pd.date_range(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        periods=n,
        freq="B",
    )
    arr = np.array(closes, dtype=float)
    return pd.DataFrame(
        {
            "Open": arr * 0.9999,
            "High": arr * 1.0010,
            "Low": arr * 0.9990,
            "Close": arr,
            "Volume": np.full(n, 1000.0),
        },
        index=dates,
    )


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """100 rows with a steady uptrend."""
    return _make_ohlcv([1.1000 + i * 0.0010 for i in range(100)])


@pytest.fixture
def flat_ohlcv() -> pd.DataFrame:
    """100 rows of flat price — indicators should produce HOLD."""
    return _make_ohlcv([1.1000] * 100)


@pytest.fixture
def oversold_ohlcv() -> pd.DataFrame:
    """85 flat rows then a sharp 15-day decline — RSI should be < 30."""
    return _make_ohlcv([1.1000] * 85 + [1.1000 - i * 0.0100 for i in range(1, 16)])


@pytest.fixture
def overbought_ohlcv() -> pd.DataFrame:
    """85 flat rows then a sharp 15-day rally — RSI should be > 70."""
    return _make_ohlcv([1.1000] * 85 + [1.1000 + i * 0.0100 for i in range(1, 16)])
