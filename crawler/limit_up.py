import logging

import numpy as np
import pandas as pd

from config import CLEANED_DIR, EASTMONEY_LIMIT_POOL_API, RAW_DIR
from utils import EastmoneyClient, amount_to_yi, is_main_board_code, normalize_time, save_csv, standardize_code, standardize_date, trading_days

logger = logging.getLogger(__name__)


def _parse_pool_rows(rows: list[dict], date: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    rename_map = {
        "c": "code",
        "n": "name",
        "p": "close",
        "zdp": "pct_chg",
        "lbc": "limit_up_streak",
        "fbt": "first_seal_time",
        "lbt": "last_seal_time",
        "zbc": "break_seal_count",
        "fund": "seal_amount",
        "amount": "amount",
        "hs": "turnover_rate",
        "lb": "volume_ratio",
    }
    df = df.rename(columns=rename_map)
    keep = [c for c in rename_map.values() if c in df.columns]
    df = df[keep].copy()
    df.insert(0, "date", standardize_date(date))
    df["code"] = df["code"].map(standardize_code)
    df = df[df["code"].map(is_main_board_code)]
    df = df[~df["name"].astype(str).str.contains("ST", case=False, na=False)]
    df["is_sealed"] = True
    df["is_broken"] = False
    df["limit_up_type"] = df["limit_up_streak"].apply(lambda x: f"{int(x)}板" if pd.notna(x) else np.nan)
    for col in ("first_seal_time", "last_seal_time"):
        if col in df.columns:
            df[col] = df[col].map(normalize_time)
    for col in ("seal_amount", "amount"):
        if col in df.columns:
            df[col] = df[col].map(amount_to_yi)
    for col in ("turnover_rate", "pct_chg"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce") / 100

    # TODO: 东方财富涨停池不稳定地返回封单量、封单比、委比。可用 AkShare
    # stock_zt_pool_em / stock_zt_pool_previous_em 补充，或用逐笔/盘口数据自行计算。
    for col in ("seal_volume", "seal_ratio", "order_book_imbalance", "late_sealed"):
        if col not in df.columns:
            df[col] = np.nan
    return df


def fetch_limit_up_samples(start_date: str, end_date: str, force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "limit_up.csv"
    raw_path = RAW_DIR / f"limit_up_{start_date}_{end_date}.csv"
    if cleaned_path.exists() and not force:
        logger.info("limit-up cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    frames = []
    for date in trading_days(start_date, end_date):
        params = {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": 0,
            "pagesize": 500,
            "sort": "fbt:asc",
            "date": date.replace("-", ""),
        }
        try:
            data = client.get_json(EASTMONEY_LIMIT_POOL_API, params)
            rows = data.get("data", {}).get("pool") or data.get("pool") or []
            frames.append(_parse_pool_rows(rows, date))
        except Exception as exc:
            logger.warning("limit-up failed date=%s error=%s", date, exc)

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    return df


def enrich_touch_samples_from_daily(limit_df: pd.DataFrame, daily_df: pd.DataFrame) -> pd.DataFrame:
    """Include intraday touched-limit but closed-open-board names when daily high reaches theoretical limit.

    TODO: 主板 10% 涨停价在 ST、新股、复牌等情况下有例外。这里仅作为可运行兜底；
    高精度研究建议用交易所涨跌停价或 AkShare/Tushare 涨跌停价表校验。
    """
    if daily_df.empty:
        return limit_df
    d = daily_df.sort_values(["code", "date"]).copy()
    d["pre_close"] = d.groupby("code")["close"].shift(1)
    d["limit_price_est"] = (d["pre_close"] * 1.10).round(2)
    touched = d[(d["high"] >= d["limit_price_est"]) & d["pre_close"].notna()].copy()
    touched["is_sealed"] = touched["close"] >= touched["limit_price_est"]
    touched["is_broken"] = ~touched["is_sealed"]
    touched = touched[["date", "code", "is_sealed", "is_broken"]]
    out = touched.merge(limit_df, on=["date", "code"], how="left", suffixes=("_daily", ""))
    for col in ("is_sealed", "is_broken"):
        out[col] = out[col].combine_first(out[f"{col}_daily"]) if col in out else out[f"{col}_daily"]
        out = out.drop(columns=[f"{col}_daily"], errors="ignore")
    return out


