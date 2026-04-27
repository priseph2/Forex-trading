import numpy as np
import pandas as pd
import pytest

from src.indicators.bollinger import calculate_bollinger_bands
from src.indicators.ema import calculate_ema
from src.indicators.macd import calculate_macd
from src.indicators.rsi import calculate_rsi


@pytest.fixture
def price_series() -> pd.Series:
    return pd.Series([1.1000 + i * 0.0010 for i in range(100)], dtype=float)


def test_ema_length_preserved(price_series):
    assert len(calculate_ema(price_series, 20)) == len(price_series)


def test_ema_returns_series(price_series):
    assert isinstance(calculate_ema(price_series, 20), pd.Series)


def test_ema_index_preserved(price_series):
    result = calculate_ema(price_series, 20)
    assert result.index.equals(price_series.index)


def test_rsi_bounds(price_series):
    rsi = calculate_rsi(price_series)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_length_preserved(price_series):
    assert len(calculate_rsi(price_series)) == len(price_series)


def test_rsi_strong_uptrend_is_high():
    steep = pd.Series([1.0 + i * 0.05 for i in range(50)], dtype=float)
    rsi = calculate_rsi(steep)
    assert float(rsi.iloc[-1]) > 70


def test_rsi_strong_downtrend_is_low():
    steep = pd.Series([3.0 - i * 0.05 for i in range(50)], dtype=float)
    rsi = calculate_rsi(steep)
    assert float(rsi.iloc[-1]) < 30


def test_macd_columns(price_series):
    result = calculate_macd(price_series)
    assert set(result.columns) == {"macd", "signal", "histogram"}


def test_macd_length_preserved(price_series):
    assert len(calculate_macd(price_series)) == len(price_series)


def test_macd_histogram_equals_difference(price_series):
    df = calculate_macd(price_series)
    np.testing.assert_allclose(
        df["histogram"].values, (df["macd"] - df["signal"]).values
    )


def test_bollinger_columns(price_series):
    result = calculate_bollinger_bands(price_series)
    assert set(result.columns) == {"upper", "middle", "lower"}


def test_bollinger_upper_gt_lower(price_series):
    bands = calculate_bollinger_bands(price_series)
    valid = bands.dropna()
    assert (valid["upper"] > valid["lower"]).all()


def test_bollinger_flat_price_zero_width():
    flat = pd.Series([1.1000] * 100, dtype=float)
    bands = calculate_bollinger_bands(flat)
    valid = bands.dropna()
    np.testing.assert_allclose(valid["upper"].values, valid["lower"].values, atol=1e-10)


def test_bollinger_length_preserved(price_series):
    assert len(calculate_bollinger_bands(price_series)) == len(price_series)
