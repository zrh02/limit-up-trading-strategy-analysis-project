import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd
import requests

from config import (
    CLEANED_DIR,
    DATA_DIR,
    RAW_DIR,
    REQUEST_INTERVAL_SECONDS,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


def setup_logging() -> None:
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8"),
        ],
    )


def ensure_dirs() -> None:
    for path in (RAW_DIR, CLEANED_DIR, DATA_DIR / "processed", DATA_DIR / "logs"):
        path.mkdir(parents=True, exist_ok=True)


def standardize_code(value: Any) -> str:
    if pd.isna(value):
        return np.nan
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[-6:].zfill(6)


def standardize_date(value: Any) -> str:
    if pd.isna(value):
        return np.nan
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def eastmoney_sec_id(code: str) -> str:
    code = standardize_code(code)
    market = "1" if code.startswith("6") else "0"
    return f"{market}.{code}"


def is_main_board_code(code: str) -> bool:
    code = standardize_code(code)
    return code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))


def amount_to_yi(value: Any) -> float:
    if pd.isna(value) or value in ("-", ""):
        return np.nan
    return float(value) / 100000000


def percent_to_decimal(value: Any) -> float:
    if pd.isna(value) or value in ("-", ""):
        return np.nan
    if isinstance(value, str):
        value = value.strip().replace("%", "")
    return float(value) / 100


def normalize_time(value: Any) -> Any:
    if pd.isna(value) or value in ("-", "", 0, "0"):
        return np.nan
    text = str(value).strip()
    if text.isdigit() and len(text) in (5, 6):
        text = text.zfill(6)
        return f"{text[:2]}:{text[2:4]}:{text[4:6]}"
    try:
        return pd.to_datetime(text).strftime("%H:%M:%S")
    except Exception:
        return text


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def read_csv_if_exists(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path, dtype={"code": str})
    return None


def winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    low, high = series.quantile([lower, upper])
    return series.clip(low, high)


def winsorize_df(
    df: pd.DataFrame,
    columns: Iterable[str],
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = winsorize_series(pd.to_numeric(out[col], errors="coerce"), lower, upper)
    return out


def trading_days(start_date: str, end_date: str, calendar_df: pd.DataFrame | None = None) -> list[str]:
    if calendar_df is not None and "date" in calendar_df.columns:
        dates = pd.to_datetime(calendar_df["date"])
        mask = (dates >= pd.to_datetime(start_date)) & (dates <= pd.to_datetime(end_date))
        return [d.strftime("%Y-%m-%d") for d in dates.loc[mask].sort_values()]
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start_date, end_date)]


class EastmoneyClient:
    def __init__(self, cache_dir: Path = RAW_DIR / "http_cache") -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://quote.eastmoney.com/"})
        self._last_request_at = 0.0
        self.logger = logging.getLogger(self.__class__.__name__)

    def _cache_path(self, url: str, params: dict[str, Any]) -> Path:
        payload = json.dumps({"url": url, "params": params}, sort_keys=True, ensure_ascii=False)
        key = hashlib.md5(payload.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def get_json(self, url: str, params: dict[str, Any], use_cache: bool = True) -> dict[str, Any]:
        cache_path = self._cache_path(url, params)
        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        for attempt in range(1, REQUEST_RETRIES + 1):
            elapsed = time.time() - self._last_request_at
            if elapsed < REQUEST_INTERVAL_SECONDS:
                time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
            try:
                self._last_request_at = time.time()
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                data = response.json()
                cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data
            except Exception as exc:
                self.logger.warning("request failed attempt=%s url=%s error=%s", attempt, url, exc)
                if attempt == REQUEST_RETRIES:
                    raise
                time.sleep(1.5 * attempt)
        raise RuntimeError("unreachable")


def run_step(name: str, func: Callable[[], Any]) -> Any:
    logger = logging.getLogger("pipeline")
    started = datetime.now()
    logger.info("start %s", name)
    result = func()
    logger.info("finish %s elapsed=%s", name, datetime.now() - started)
    return result

