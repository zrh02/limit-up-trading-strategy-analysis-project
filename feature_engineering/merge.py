import logging

import pandas as pd

from config import PROCESSED_DIR
from utils import save_csv, standardize_code, standardize_date

logger = logging.getLogger(__name__)


def _normalize_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" in out.columns:
        out["date"] = out["date"].map(standardize_date)
    if "code" in out.columns:
        out["code"] = out["code"].map(standardize_code)
    return out


def merge_model_dataset(
    samples: pd.DataFrame,
    basic_panel: pd.DataFrame,
    money_flow: pd.DataFrame,
    trend: pd.DataFrame,
    sector: pd.DataFrame,
    market: pd.DataFrame,
    targets: pd.DataFrame,
    force: bool = False,
) -> pd.DataFrame:
    output_path = PROCESSED_DIR / "model_dataset.csv"
    if output_path.exists() and not force:
        return pd.read_csv(output_path, dtype={"code": str})

    dataset = _normalize_key(samples).drop_duplicates(["date", "code"])
    for frame in (basic_panel, money_flow, trend, sector, targets):
        if frame is not None and not frame.empty:
            dataset = dataset.merge(_normalize_key(frame), on=["date", "code"], how="left")
    if market is not None and not market.empty:
        dataset = dataset.merge(_normalize_key(market), on="date", how="left")

    preferred_first = ["date", "code", "name", "is_sealed", "is_broken", "limit_up_type"]
    ordered = [c for c in preferred_first if c in dataset.columns] + [c for c in dataset.columns if c not in preferred_first]
    dataset = dataset[ordered].sort_values(["date", "code"])
    save_csv(dataset, output_path)
    return dataset

