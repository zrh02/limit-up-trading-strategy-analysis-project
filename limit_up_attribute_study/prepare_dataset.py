import numpy as np
import pandas as pd

from config import ATTRIBUTE_DATA, DATA_DIR, SOURCE_DATA


COLUMN_MAP = {
    "date": "日期",
    "code": "股票代码",
    "name": "股票名称",
    "limit_up_streak": "连板数",
    "first_seal_time": "第一次封板时间",
    "last_seal_time": "最后封板时间",
    "break_seal_count": "炸板次数",
    "late_sealed": "尾盘是否封板",
    "seal_amount": "封单金额_亿元",
    "seal_volume": "封单量",
    "seal_ratio": "封单比",
    "next_open_return": "第二日开盘收益",
    "next_high_return": "第二日最高收益",
    "next_low_return": "第二日最低收益",
    "next_close_return": "第二日收盘收益",
    "third_day_return": "第三日收益",
    "is_next_limit_up": "是否连板",
}


def to_seconds(value):
    if pd.isna(value):
        return np.nan
    parts = str(value).split(":")
    if len(parts) != 3:
        return np.nan
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def board_type(streak):
    if pd.isna(streak):
        return np.nan
    streak = int(streak)
    if streak == 1:
        return "首板"
    if streak == 2:
        return "二板"
    if streak == 3:
        return "三板"
    return "N板"


def time_bucket(seconds):
    if pd.isna(seconds):
        return np.nan
    if seconds <= 9 * 3600 + 30 * 60:
        return "09:25-09:30"
    if seconds <= 10 * 3600:
        return "09:30-10:00"
    if seconds <= 11 * 3600 + 30 * 60:
        return "10:00-11:30"
    if seconds <= 14 * 3600:
        return "13:00-14:00"
    return "14:00-15:00"


def break_bucket(count):
    if pd.isna(count):
        return np.nan
    if count == 0:
        return "0次"
    if count == 1:
        return "1次"
    if count <= 3:
        return "2-3次"
    return "4次及以上"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(SOURCE_DATA, dtype={"code": str}, low_memory=False)
    missing = [col for col in COLUMN_MAP if col not in source.columns]
    if missing:
        raise KeyError(f"源数据缺少字段: {missing}")

    df = source[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
    df["涨停类型"] = df["连板数"].map(board_type)
    df["第一次封板秒数"] = df["第一次封板时间"].map(to_seconds)
    df["最后封板秒数"] = df["最后封板时间"].map(to_seconds)
    df["第一次封板分钟_距0930"] = (df["第一次封板秒数"] - (9 * 3600 + 30 * 60)) / 60
    df["最后封板分钟_距0930"] = (df["最后封板秒数"] - (9 * 3600 + 30 * 60)) / 60
    df["首封时间段"] = df["第一次封板秒数"].map(time_bucket)
    df["炸板次数分组"] = df["炸板次数"].map(break_bucket)

    # 本研究只使用有涨停属性字段的样本；缺失值保留，便于后续质量报告说明。
    df.to_csv(ATTRIBUTE_DATA, index=False, encoding="utf-8-sig")
    print(f"saved: {ATTRIBUTE_DATA}")
    print(f"rows: {len(df):,}")
    print(df.notna().sum().to_string())


if __name__ == "__main__":
    main()

