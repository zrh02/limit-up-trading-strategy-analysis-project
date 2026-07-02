import logging

import pandas as pd

from config import CLEANED_DIR, EASTMONEY_QUOTE_API, MAIN_BOARD_MARKET_FILTER, RAW_DIR
from utils import EastmoneyClient, amount_to_yi, is_main_board_code, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


FIELDS = "f12,f14,f20,f21,f9,f23,f26"


def fetch_stock_basic(force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "basic.csv"
    raw_path = RAW_DIR / "basic.csv"
    if cleaned_path.exists() and not force:
        logger.info("basic cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    rows = []
    page = 1
    while True:
        params = {
            "pn": page,
            "pz": 200,
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": MAIN_BOARD_MARKET_FILTER,
            "fields": FIELDS,
        }
        data = client.get_json(EASTMONEY_QUOTE_API, params)
        diff = (data.get("data") or {}).get("diff") or []
        if not diff:
            break
        rows.extend(diff)
        if len(diff) < 200:
            break
        page += 1

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(
        columns={
            "f12": "code",
            "f14": "name",
            "f20": "total_market_cap",
            "f21": "float_market_cap",
            "f9": "pe",
            "f23": "pb",
            "f26": "list_date",
        }
    )
    df["code"] = df["code"].map(standardize_code)
    df = df[df["code"].map(is_main_board_code)]
    df["total_market_cap"] = df["total_market_cap"].map(amount_to_yi)
    df["float_market_cap"] = df["float_market_cap"].map(amount_to_yi)
    df["list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    df["pe"] = pd.to_numeric(df["pe"], errors="coerce")
    df["pb"] = pd.to_numeric(df["pb"], errors="coerce")
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    return df[["code", "name", "total_market_cap", "float_market_cap", "pe", "pb", "list_date"]]


def add_listing_days(panel: pd.DataFrame, basic: pd.DataFrame) -> pd.DataFrame:
    out = panel.merge(basic, on="code", how="left")
    out["date"] = out["date"].map(standardize_date)
    out["listing_days"] = (pd.to_datetime(out["date"]) - pd.to_datetime(out["list_date"])).dt.days
    return out

