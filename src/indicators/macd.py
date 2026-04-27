import pandas as pd

from src.indicators.ema import calculate_ema


def calculate_macd(
    series: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """Returns DataFrame with columns: macd, signal, histogram."""
    fast = calculate_ema(series, fast_period)
    slow = calculate_ema(series, slow_period)
    macd_line = fast - slow
    signal_line = calculate_ema(macd_line, signal_period)
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": macd_line - signal_line,
        },
        index=series.index,
    )
