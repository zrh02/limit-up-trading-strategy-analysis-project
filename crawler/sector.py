import logging

import numpy as np
import pandas as pd

from config import CLEANED_DIR, EASTMONEY_BOARD_API, RAW_DIR
from utils import EastmoneyClient, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


def fetch_sector_snapshot(date: str, force: bool = False) -> pd.DataFrame:
    """Fetch industry board returns for a date-like snapshot.

    TODO: 东方财富公开板块接口通常返回实时或最近交易日快照，不保证可回溯任意历史日。
    严格历史研究建议替代方案：AkShare stock_board_industry_hist_em、Tushare 行业指数、
    或每日运行本模块沉淀快照。
    """
    cleaned_path = CLEANED_DIR / f"sector_snapshot_{date}.csv"
    if cleaned_path.exists() and not force:
        return pd.read_csv(cleaned_path)

    client = EastmoneyClient()
    params = {
        "pn": 1,
        "pz": 200,
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f3",
    }
    data = client.get_json(EASTMONEY_BOARD_API, params)
    diff = (data.get("data") or {}).get("diff") or []
    df = pd.DataFrame(diff).rename(columns={"f12": "industry_code", "f14": "industry_name", "f3": "industry_return"})
    if df.empty:
        return df
    df.insert(0, "date", standardize_date(date))
    df["industry_return"] = pd.to_numeric(df["industry_return"], errors="coerce") / 100
    df["industry_rank"] = df["industry_return"].rank(ascending=False, method="dense")
    save_csv(df, RAW_DIR / f"sector_snapshot_{date}.csv")
    save_csv(df, cleaned_path)
    return df


def build_sector_features(limit_df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    """Create stock-date sector feature placeholders and available snapshot-level features.

    东方财富个股所属行业/概念历史归属接口公开稳定性较弱。这里保留可合并字段位，
    缺失为 NaN，避免伪造板块信息。
    """
    cleaned_path = CLEANED_DIR / "sector_features.csv"
    if cleaned_path.exists() and not force:
        return pd.read_csv(cleaned_path, dtype={"code": str})

    base = limit_df[["date", "code"]].drop_duplicates().copy()
    base["code"] = base["code"].map(standardize_code)
    base["date"] = base["date"].map(standardize_date)
    base["industry_return"] = np.nan
    base["industry_rank"] = np.nan
    base["concept_return"] = np.nan
    base["concept_limit_up_count"] = np.nan
    base["concept_count"] = np.nan
    # TODO: 可用 AkShare stock_board_concept_cons_em 获取个股概念归属，
    # 再与概念板块历史行情合并计算 concept_return / concept_limit_up_count。
    save_csv(base, cleaned_path)
    return base

