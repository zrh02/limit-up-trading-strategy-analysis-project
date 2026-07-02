import logging

import pandas as pd

from config import CLEANED_DIR
from utils import save_csv

logger = logging.getLogger(__name__)


def calculate_trend_factors(daily_df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "trend_factors.csv"
    if cleaned_path.exists() and not force:
        return pd.read_csv(cleaned_path, dtype={"code": str})

    df = daily_df.copy()
    if df.empty:
        return pd.DataFrame(columns=["date", "code"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    g = df.groupby("code", group_keys=False)

    for n in (5, 10, 20):
        df[f"return_{n}d"] = g["close"].pct_change(n)
    for n in (5, 10):
        df[f"volume_change_{n}d"] = g["volume"].pct_change(n)

    df["is_60d_high"] = df["close"] >= g["high"].rolling(60, min_periods=1).max().reset_index(level=0, drop=True)
    df["up_day"] = df["close"] > g["close"].shift(1)
    df["positive_candle"] = df["close"] > df["open"]
    df["consecutive_up_days"] = g["up_day"].transform(_consecutive_true)
    df["consecutive_positive_candles"] = g["positive_candle"].transform(_consecutive_true)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    cols = [
        "date",
        "code",
        "return_5d",
        "return_10d",
        "return_20d",
        "volume_change_5d",
        "volume_change_10d",
        "is_60d_high",
        "consecutive_up_days",
        "consecutive_positive_candles",
    ]
    out = df[cols]
    save_csv(out, cleaned_path)
    return out


def _consecutive_true(series: pd.Series) -> pd.Series:
    counts = []
    current = 0
    for value in series.fillna(False):
        current = current + 1 if bool(value) else 0
        counts.append(current)
    return pd.Series(counts, index=series.index)

