import pandas as pd


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """EMA using adjust=False to match the industry-standard Wilder/MetaTrader formula."""
    return series.ewm(span=period, adjust=False).mean()
