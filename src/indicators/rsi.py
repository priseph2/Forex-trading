import pandas as pd


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI using Wilder's smoothing (ewm alpha=1/period), matching Bloomberg/MetaTrader."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
