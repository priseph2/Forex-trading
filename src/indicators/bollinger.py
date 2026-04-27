import pandas as pd


def calculate_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Returns DataFrame with columns: upper, middle, lower. Uses ddof=0 (population std)."""
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std(ddof=0)
    return pd.DataFrame(
        {
            "upper": middle + num_std * std,
            "middle": middle,
            "lower": middle - num_std * std,
        },
        index=series.index,
    )
