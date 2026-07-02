import logging

import numpy as np
import pandas as pd

from config import CLEANED_DIR, EASTMONEY_MONEY_FLOW_API, RAW_DIR
from utils import EastmoneyClient, amount_to_yi, eastmoney_sec_id, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


MONEY_COLUMNS = [
    "date",
    "main_net_inflow",
    "small_net_inflow",
    "medium_net_inflow",
    "large_net_inflow",
    "super_large_net_inflow",
    "main_net_inflow_ratio",
    "small_net_inflow_ratio",
    "medium_net_inflow_ratio",
    "large_net_inflow_ratio",
    "super_large_net_inflow_ratio",
]


def fetch_money_flow_for_code(code: str, start_date: str, end_date: str, client: EastmoneyClient | None = None) -> pd.DataFrame:
    client = client or EastmoneyClient()
    code = standardize_code(code)
    params = {
        "lmt": 0,
        "klt": 101,
        "secid": eastmoney_sec_id(code),
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    data = client.get_json(EASTMONEY_MONEY_FLOW_API, params)
    rows = ((data.get("data") or {}).get("klines")) or []
    parsed = [row.split(",") for row in rows]
    df = pd.DataFrame(parsed, columns=MONEY_COLUMNS)
    if df.empty:
        return df
    df["date"] = df["date"].map(standardize_date)
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
    df.insert(1, "code", code)
    amount_cols = [c for c in df.columns if c.endswith("inflow")]
    ratio_cols = [c for c in df.columns if c.endswith("ratio")]
    for col in amount_cols:
        df[col] = df[col].map(amount_to_yi)
    for col in ratio_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce") / 100
    return df


def fetch_money_flow(codes: list[str], start_date: str, end_date: str, force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "money_flow.csv"
    raw_path = RAW_DIR / f"money_flow_{start_date}_{end_date}.csv"
    if cleaned_path.exists() and not force:
        logger.info("money-flow cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    frames = []
    for idx, code in enumerate(codes, start=1):
        try:
            frames.append(fetch_money_flow_for_code(code, start_date, end_date, client))
        except Exception as exc:
            logger.warning("money-flow failed code=%s error=%s", code, exc)
        if idx % 100 == 0:
            logger.info("money-flow progress %s/%s", idx, len(codes))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "code"])
    df = df.replace("-", np.nan)
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    return df

