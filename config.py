from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
PROCESSED_DIR = DATA_DIR / "processed"

START_DATE = "2025-06-01"
END_DATE = "2026-06-30"

REQUEST_INTERVAL_SECONDS = 0.6
REQUEST_TIMEOUT_SECONDS = 15
REQUEST_RETRIES = 3

# 东方财富公开接口字段可能调整。需要更高稳定性时可替换为 AkShare/Tushare 数据源。
EASTMONEY_QUOTE_API = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_KLINE_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_BOARD_API = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_LIMIT_POOL_API = "https://push2ex.eastmoney.com/getTopicZTPool"
EASTMONEY_MONEY_FLOW_API = "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

MAIN_BOARD_MARKET_FILTER = "(m:1+t:2),(m:0+t:6)"

