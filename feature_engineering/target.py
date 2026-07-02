import logging

import pandas as pd

from config import CLEANED_DIR
from utils import save_csv

logger = logging.getLogger(__name__)


def generate_targets(sample_df: pd.DataFrame, daily_df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "targets.csv"
    if cleaned_path.exists() and not force:
        return pd.read_csv(cleaned_path, dtype={"code": str})

    d = daily_df.copy()
    if d.empty or sample_df.empty:
        return pd.DataFrame(columns=["date", "code"])
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["code", "date"])
    g = d.groupby("code")
    for col in ("open", "high", "low", "close"):
        d[f"next_{col}"] = g[col].shift(-1)
    d["third_close"] = g["close"].shift(-2)
    d["next_limit_est"] = (d["close"] * 1.10).round(2)
    d["is_next_limit_up"] = g["high"].shift(-1) >= d["next_limit_est"]

    target = d[[
        "date",
        "code",
        "close",
        "next_open",
        "next_high",
        "next_low",
        "next_close",
        "third_close",
        "is_next_limit_up",
    ]].copy()
    target["next_open_return"] = target["next_open"] / target["close"] - 1
    target["next_high_return"] = target["next_high"] / target["close"] - 1
    target["next_low_return"] = target["next_low"] / target["close"] - 1
    target["next_close_return"] = target["next_close"] / target["close"] - 1
    target["third_day_return"] = target["third_close"] / target["close"] - 1
    target["date"] = target["date"].dt.strftime("%Y-%m-%d")

    keys = sample_df[["date", "code"]].drop_duplicates()
    out = keys.merge(target, on=["date", "code"], how="left")
    out = out.drop(columns=["close", "next_open", "next_high", "next_low", "next_close", "third_close"])
    save_csv(out, cleaned_path)
    return out

