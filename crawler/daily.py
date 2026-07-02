import logging

import pandas as pd

from config import CLEANED_DIR, EASTMONEY_KLINE_API, RAW_DIR
from utils import EastmoneyClient, eastmoney_sec_id, is_main_board_code, save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


KLINE_COLUMNS = ["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover_rate"]
DAILY_COLUMNS = ["date", "code", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]


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
        return pd.DataFrame(columns=DAILY_COLUMNS)
    df.insert(1, "code", code)
    df["date"] = df["date"].map(standardize_date)
    numeric_cols = [c for c in df.columns if c not in ("date", "code")]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    return df[DAILY_COLUMNS]


def _fetch_codes_once(
    codes: list[str],
    start_date: str,
    end_date: str,
    client: EastmoneyClient,
    label: str,
) -> tuple[list[pd.DataFrame], list[str]]:
    frames: list[pd.DataFrame] = []
    failed_codes: list[str] = []
    for idx, raw_code in enumerate(codes, start=1):
        code = standardize_code(raw_code)
        if not is_main_board_code(code):
            continue
        try:
            df_code = fetch_daily_for_code(code, start_date, end_date, client)
            if df_code.empty:
                failed_codes.append(code)
            else:
                frames.append(df_code)
        except Exception as exc:
            logger.warning("daily %s failed code=%s error=%s", label, code, exc)
            failed_codes.append(code)
        if idx % 50 == 0:
            logger.info("daily %s progress %s/%s", label, idx, len(codes))
    return frames, sorted(set(failed_codes))


def fetch_daily_history(
    codes: list[str],
    start_date: str,
    end_date: str,
    force: bool = False,
) -> pd.DataFrame:
    raw_path = RAW_DIR / f"daily_{start_date}_{end_date}.csv"
    cleaned_path = CLEANED_DIR / "daily.csv"
    failed_path = CLEANED_DIR / "daily_failed_codes.csv"
    if cleaned_path.exists() and not force:
        logger.info("daily cache hit %s", cleaned_path)
        return pd.read_csv(cleaned_path, dtype={"code": str})

    client = EastmoneyClient()
    frames, failed_codes = _fetch_codes_once(codes, start_date, end_date, client, "initial")

    if failed_codes:
        logger.info("retry daily failed codes count=%s", len(failed_codes))
        retry_frames, failed_codes = _fetch_codes_once(failed_codes, start_date, end_date, client, "retry")
        frames.extend(retry_frames)

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DAILY_COLUMNS)
    if not df.empty:
        df = df.drop_duplicates(["date", "code"]).sort_values(["code", "date"])

    save_csv(pd.DataFrame({"code": failed_codes}), failed_path)
    if failed_codes:
        logger.warning("daily failed codes saved path=%s count=%s", failed_path, len(failed_codes))
    save_csv(df, raw_path)
    save_csv(df, cleaned_path)
    return df
