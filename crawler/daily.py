import logging

import pandas as pd

from config import CLEANED_DIR, EASTMONEY_KLINE_API, RAW_DIR
from utils import EastmoneyClient, eastmoney_sec_id, is_main_board_code, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


KLINE_COLUMNS = ["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover_rate"]


def fetch_daily_for_code(code: str, start_date: str, end_date: str, client: EastmoneyClient | None = None) -> pd.DataFrame:
    client = client or EastmoneyClient()
    code = standardize_code(code)
    params = {
        "secid": eastmoney_sec_id(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
    }
    data = client.get_json(EASTMONEY_KLINE_API, params)
    klines = (data.get("data") or {}).get("klines") or []
    rows = [line.split(",") for line in klines]
    df = pd.DataFrame(rows, columns=KLINE_COLUMNS)
    if df.empty:
        return df
    df.insert(1, "code", code)
    df["date"] = df["date"].map(standardize_date)
    numeric_cols = [c for c in df.columns if c not in ("date", "code")]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    return df[["date", "code", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]]


def fetch_daily_history(
    codes: list[str],
    start_date: str,
    end_date: str,
    force: bool = False,
) -> pd.DataFrame:
    raw_path = RAW_DIR / f"daily_{start_date}_{end_date}.csv"
    cleaned_path = CLEANED_DIR / "daily.csv"
    if cleaned_path.exists() and not force:
        logger.info("daily cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    frames = []
    for idx, code in enumerate(codes, start=1):
        code = standardize_code(code)
        if not is_main_board_code(code):
            continue
        try:
            frames.append(fetch_daily_for_code(code, start_date, end_date, client))
        except Exception as exc:
            logger.warning("daily failed code=%s error=%s", code, exc)
        if idx % 100 == 0:
            logger.info("daily progress %s/%s", idx, len(codes))

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "code"])
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    return df

