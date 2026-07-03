import logging
import math

import pandas as pd

from config import CLEANED_DIR, EASTMONEY_QUOTE_API, END_DATE, MAIN_BOARD_MARKET_FILTER, RAW_DIR
from utils import EastmoneyClient, amount_to_yi, is_main_board_code, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


FIELDS = "f12,f14,f20,f21,f9,f23,f26"
BASIC_COLUMNS = ["code", "name", "total_market_cap", "float_market_cap", "pe", "pb", "list_date"]


def _is_valid_research_stock(row: pd.Series) -> bool:
    name = str(row.get("name", ""))
    if any(token in name.upper() for token in ("ST", "*ST", "PT")):
        return False
    if any(token in name for token in ("退", "N", "C")):
        return False
    list_date = pd.to_datetime(row.get("list_date"), errors="coerce")
    if pd.notna(list_date) and list_date > pd.to_datetime(END_DATE):
        return False
    return is_main_board_code(row.get("code"))


def fetch_stock_basic(force: bool = False) -> pd.DataFrame:
    cleaned_path = CLEANED_DIR / "basic.csv"
    raw_path = RAW_DIR / "basic.csv"
    if cleaned_path.exists() and not force:
        logger.info("basic cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    rows = []
    page = 1
    page_size = 100
    total = None
    while True:
        params = {
            "pn": page,
            "pz": page_size,
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": MAIN_BOARD_MARKET_FILTER,
            "fields": FIELDS,
        }
        data = client.get_json(EASTMONEY_QUOTE_API, params, use_cache=not force)
        payload = data.get("data") or {}
        diff = payload.get("diff") or []
        if total is None:
            total = int(payload.get("total") or 0)
            logger.info("stock basic total=%s", total)
        if not diff:
            break
        rows.extend(diff)
        if total and page >= math.ceil(total / page_size):
            break
        page += 1

    df = pd.DataFrame(rows)
    if df.empty:
        logger.error("stock basic endpoint returned no rows; check Eastmoney fs/fields params or network response")
        empty = pd.DataFrame(columns=BASIC_COLUMNS)
        save_csv(empty, raw_path)
        save_csv(empty, cleaned_path)
        return empty

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
    df["list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    df = df[df.apply(_is_valid_research_stock, axis=1)].copy()
    df["total_market_cap"] = df["total_market_cap"].map(amount_to_yi)
    df["float_market_cap"] = df["float_market_cap"].map(amount_to_yi)
    df["pe"] = pd.to_numeric(df["pe"], errors="coerce")
    df["pb"] = pd.to_numeric(df["pb"], errors="coerce")
    df = df.drop_duplicates("code").sort_values("code")
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    logger.info("stock basic cleaned rows=%s", len(df))
    return df[BASIC_COLUMNS]


def add_listing_days(panel: pd.DataFrame, basic: pd.DataFrame) -> pd.DataFrame:
    out = panel.merge(basic, on="code", how="left")
    out["date"] = out["date"].map(standardize_date)
    out["listing_days"] = (pd.to_datetime(out["date"]) - pd.to_datetime(out["list_date"])).dt.days
    return out

