import argparse
import logging
from datetime import timedelta

import pandas as pd

from config import END_DATE, START_DATE
from crawler.basic import add_listing_days, fetch_stock_basic
from crawler.daily import fetch_daily_history
from crawler.limit_up import enrich_touch_samples_from_daily, fetch_limit_up_samples
from crawler.market import fetch_market_environment
from crawler.money_flow import fetch_money_flow
from crawler.sector import build_sector_features
from feature_engineering.merge import merge_model_dataset
from feature_engineering.target import generate_targets
from feature_engineering.trend_factor import calculate_trend_factors
from utils import ensure_dirs, run_step, save_csv, setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A-share main-board limit-up quantitative research pipeline")
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument("--end-date", default=END_DATE)
    parser.add_argument("--force", action="store_true", help="ignore local CSV cache and refetch/recompute")
    parser.add_argument("--skip-crawl", action="store_true", help="reuse cleaned data and only rebuild features/dataset")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    setup_logging()

    feature_start = (pd.to_datetime(args.start_date) - timedelta(days=120)).strftime("%Y-%m-%d")
    target_end = (pd.to_datetime(args.end_date) + timedelta(days=10)).strftime("%Y-%m-%d")

    if not args.skip_crawl:
        basic = run_step("fetch basic", lambda: fetch_stock_basic(force=args.force))
        codes = sorted(basic["code"].dropna().unique().tolist())
        daily = run_step("fetch daily", lambda: fetch_daily_history(codes, feature_start, target_end, force=args.force))
        limit_pool = run_step("fetch limit-up pool", lambda: fetch_limit_up_samples(args.start_date, args.end_date, force=args.force))
        samples = run_step("enrich touch samples", lambda: enrich_touch_samples_from_daily(limit_pool, daily))
        samples = samples[(samples["date"] >= args.start_date) & (samples["date"] <= args.end_date)].copy()
        basic_name = basic[["code", "name"]].drop_duplicates()
        samples = samples.merge(basic_name, on="code", how="left", suffixes=("", "_basic"))
        if "name_basic" in samples.columns:
            samples["name"] = samples["name"].combine_first(samples["name_basic"])
            samples = samples.drop(columns=["name_basic"])
        save_csv(samples, __import__("config").CLEANED_DIR / "limit_up.csv")
        money_flow = run_step("fetch money flow", lambda: fetch_money_flow(codes, args.start_date, args.end_date, force=args.force))
    else:
        from config import CLEANED_DIR

        basic = pd.read_csv(CLEANED_DIR / "basic.csv", dtype={"code": str})
        daily = pd.read_csv(CLEANED_DIR / "daily.csv", dtype={"code": str})
        samples = pd.read_csv(CLEANED_DIR / "limit_up.csv", dtype={"code": str})
        money_flow = pd.read_csv(CLEANED_DIR / "money_flow.csv", dtype={"code": str})

    basic_panel = run_step("build basic panel", lambda: add_listing_days(samples[["date", "code"]], basic))
    basic_panel = basic_panel.drop(columns=["name"], errors="ignore")
    trend = run_step("trend factors", lambda: calculate_trend_factors(daily, force=args.force))
    sector = run_step("sector features", lambda: build_sector_features(samples, force=args.force))
    market = run_step(
        "market environment",
        lambda: fetch_market_environment(args.start_date, args.end_date, samples, force=args.force),
    )
    targets = run_step("targets", lambda: generate_targets(samples, daily, force=args.force))
    dataset = run_step(
        "merge model dataset",
        lambda: merge_model_dataset(samples, basic_panel, money_flow, trend, sector, market, targets, force=args.force),
    )
    logger.info("model dataset rows=%s cols=%s", len(dataset), len(dataset.columns))


if __name__ == "__main__":
    main()


