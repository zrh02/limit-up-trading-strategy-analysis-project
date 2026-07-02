import logging

import numpy as np
import pandas as pd

from config import CLEANED_DIR, EASTMONEY_KLINE_API, RAW_DIR
from utils import EastmoneyClient, save_csv, standardize_date

logger = logging.getLogger(__name__)


INDEX_SECIDS = {
    "sh_index": "1.000001",
    "sz_index": "0.399001",
}


def fetch_index_daily(secid: str, start_date: str, end_date: str, client: EastmoneyClient) -> pd.DataFrame:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
    }
    data = client.get_json(EASTMONEY_KLINE_API, params)
    rows = [x.split(",") for x in ((data.get("data") or {}).get("klines") or [])]
    df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover_rate"])
    if df.empty:
        return df
    df["date"] = df["date"].map(standardize_date)
    df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce") / 100
    return df[["date", "pct_chg"]]


def fetch_market_environment(
    start_date: str,
    end_date: str,
    limit_df: pd.DataFrame | None = None,
    force: bool = False,
) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "market_environment.csv"
    raw_path = RAW_DIR / f"market_environment_{start_date}_{end_date}.csv"
    if cleaned_path.exists() and not force:
        return pd.read_csv(cleaned_path)

    client = EastmoneyClient()
    frames = []
    for name, secid in INDEX_SECIDS.items():
        idx = fetch_index_daily(secid, start_date, end_date, client).rename(columns={"pct_chg": f"{name}_return"})
        frames.append(idx)

    env = frames[0]
    for frame in frames[1:]:
        env = env.merge(frame, on="date", how="outer")

    if limit_df is not None and not limit_df.empty:
        stat = limit_df.groupby("date").agg(
            market_limit_up_count=("code", "nunique"),
            market_break_rate=("is_broken", "mean"),
        ).reset_index()
        env = env.merge(stat, on="date", how="left")
    else:
        env["market_limit_up_count"] = np.nan
        env["market_break_rate"] = np.nan

    env = env.sort_values("date")
    save_csv(env, raw_path)
    save_csv(env, cleaned_path)
    return env

