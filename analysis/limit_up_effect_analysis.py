from pathlib import Path

import nbformat as nbf
import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "model_dataset.csv"
OUT_DIR = ROOT / "analysis" / "output"
NOTEBOOK_PATH = ROOT / "analysis" / "limit_up_effect_analysis.ipynb"

CHINESE_COLUMNS = {
    "first_seal_bucket": "首次封板时间段",
    "break_count_bucket": "炸板次数分组",
    "streak_bucket": "连板类型",
    "samples": "样本数",
    "next_open_mean": "次日开盘收益均值(%)",
    "next_high_mean": "次日最高收益均值(%)",
    "next_close_mean": "次日收盘收益均值(%)",
    "close_win_rate": "次日收盘上涨概率(%)",
    "first_seal_minutes": "首次封板距9:30分钟数",
    "seal_duration_minutes": "首封至末封间隔分钟数",
    "break_seal_count": "炸板次数",
    "limit_up_streak": "连板数",
    "next_open_return": "次日开盘收益",
    "next_high_return": "次日最高收益",
    "next_close_return": "次日收盘收益",
}


def configure_chinese_font():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def to_seconds(value):
    if pd.isna(value):
        return np.nan
    parts = str(value).split(":")
    if len(parts) != 3:
        return np.nan
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def pct(x):
    return x * 100


def bucket_first_seal(seconds):
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


def bucket_break_count(x):
    if pd.isna(x):
        return np.nan
    if x == 0:
        return "0次"
    if x == 1:
        return "1次"
    if x <= 3:
        return "2-3次"
    return "4次及以上"


def bucket_streak(x):
    if pd.isna(x):
        return np.nan
    x = int(x)
    if x == 1:
        return "首板"
    if x == 2:
        return "二板"
    return "三板及以上"


def summarize(df, group_col):
    out = (
        df.groupby(group_col, dropna=False)
        .agg(
            samples=("code", "size"),
            next_open_mean=("next_open_return", "mean"),
            next_high_mean=("next_high_return", "mean"),
            next_close_mean=("next_close_return", "mean"),
            close_win_rate=("next_close_return", lambda s: (s > 0).mean()),
        )
        .reset_index()
    )
    for col in ["next_open_mean", "next_high_mean", "next_close_mean", "close_win_rate"]:
        out[col] = out[col] * 100
    return out


def to_chinese_table(df):
    return df.rename(columns=CHINESE_COLUMNS)


def bar_chart(summary, x_col, y_cols, title, output):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(summary))
    width = 0.8 / len(y_cols)
    for i, col in enumerate(y_cols):
        ax.bar(
            x + i * width - 0.4 + width / 2,
            summary[col],
            width=width,
            label=CHINESE_COLUMNS.get(col, col),
        )
    ax.set_xticks(x)
    ax.set_xticklabels(summary[x_col].astype(str), rotation=20, ha="right")
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("收益率 / 概率（%）")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def scatter_chart(df, output):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(df["first_seal_minutes"], pct(df["next_close_return"]), s=18, alpha=0.45)
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title("首次封板时间与次日收盘收益")
    ax.set_xlabel("首次封板距 09:30 的分钟数")
    ax.set_ylabel("次日收盘收益（%）")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main():
    configure_chinese_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH, dtype={"code": str}, low_memory=False)
    core_cols = [
        "date",
        "code",
        "name",
        "limit_up_streak",
        "first_seal_time",
        "last_seal_time",
        "break_seal_count",
        "next_open_return",
        "next_high_return",
        "next_close_return",
    ]
    core = df.dropna(subset=core_cols).copy()
    core["first_seal_seconds"] = core["first_seal_time"].map(to_seconds)
    core["last_seal_seconds"] = core["last_seal_time"].map(to_seconds)
    core["first_seal_minutes"] = (core["first_seal_seconds"] - (9 * 3600 + 30 * 60)) / 60
    core["seal_duration_minutes"] = (core["last_seal_seconds"] - core["first_seal_seconds"]) / 60
    core["first_seal_bucket"] = core["first_seal_seconds"].map(bucket_first_seal)
    core["break_count_bucket"] = core["break_seal_count"].map(bucket_break_count)
    core["streak_bucket"] = core["limit_up_streak"].map(bucket_streak)

    first_order = ["09:25-09:30", "09:30-10:00", "10:00-11:30", "13:00-14:00", "14:00-15:00"]
    break_order = ["0次", "1次", "2-3次", "4次及以上"]
    streak_order = ["首板", "二板", "三板及以上"]

    by_first = summarize(core, "first_seal_bucket").set_index("first_seal_bucket").loc[first_order].reset_index()
    by_break = summarize(core, "break_count_bucket").set_index("break_count_bucket").loc[break_order].reset_index()
    by_streak = summarize(core, "streak_bucket").set_index("streak_bucket").loc[streak_order].reset_index()

    by_first_cn = to_chinese_table(by_first)
    by_break_cn = to_chinese_table(by_break)
    by_streak_cn = to_chinese_table(by_streak)

    by_first_cn.to_csv(OUT_DIR / "按首次封板时间分组.csv", index=False, encoding="utf-8-sig")
    by_break_cn.to_csv(OUT_DIR / "按炸板次数分组.csv", index=False, encoding="utf-8-sig")
    by_streak_cn.to_csv(OUT_DIR / "按连板类型分组.csv", index=False, encoding="utf-8-sig")

    # Keep stable English filenames for notebook image links.
    bar_chart(
        by_first,
        "first_seal_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "按首次封板时间分组的次日收益",
        OUT_DIR / "next_returns_by_first_seal_time.png",
    )
    bar_chart(
        by_break,
        "break_count_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "按炸板次数分组的次日收益",
        OUT_DIR / "next_returns_by_break_count.png",
    )
    bar_chart(
        by_streak,
        "streak_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "按连板类型分组的次日收益",
        OUT_DIR / "next_returns_by_streak.png",
    )
    scatter_chart(core, OUT_DIR / "first_seal_time_scatter.png")

    correlations = core[
        [
            "first_seal_minutes",
            "seal_duration_minutes",
            "break_seal_count",
            "limit_up_streak",
            "next_open_return",
            "next_high_return",
            "next_close_return",
        ]
    ].corr()
    correlations = correlations.rename(index=CHINESE_COLUMNS, columns=CHINESE_COLUMNS)
    correlations.to_csv(OUT_DIR / "相关系数矩阵.csv", encoding="utf-8-sig")

    summary_text = f"""
数据口径：
- 最终宽表总行数：{len(df):,}
- 同时具备封板细节字段和次日收益的样本数：{len(core):,}
- 样本日期范围：{core['date'].min()} 至 {core['date'].max()}

核心均值：
- 次日开盘收益均值：{pct(core['next_open_return'].mean()):.2f}%
- 次日最高收益均值：{pct(core['next_high_return'].mean()):.2f}%
- 次日收盘收益均值：{pct(core['next_close_return'].mean()):.2f}%
- 次日收盘上涨概率：{(core['next_close_return'] > 0).mean() * 100:.2f}%
"""

    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        nbf.v4.new_markdown_cell(
            "# 涨停封板细节对次日收益的影响分析\n\n"
            "本 Notebook 分析首日封板时间、炸板次数、连板类型与次日收益之间的关系。"
            "分析范围仅限东方财富涨停池中具备封板细节字段的样本。"
        ),
        nbf.v4.new_markdown_cell(summary_text),
        nbf.v4.new_code_cell(
            "import pandas as pd\n"
            "df = pd.read_csv('../data/processed/model_dataset.csv', dtype={'code': str}, low_memory=False)\n"
            "df.shape"
        ),
        nbf.v4.new_code_cell("pd.read_csv('output/按首次封板时间分组.csv')"),
        nbf.v4.new_markdown_cell("![按首次封板时间分组的次日收益](output/next_returns_by_first_seal_time.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/按炸板次数分组.csv')"),
        nbf.v4.new_markdown_cell("![按炸板次数分组的次日收益](output/next_returns_by_break_count.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/按连板类型分组.csv')"),
        nbf.v4.new_markdown_cell("![按连板类型分组的次日收益](output/next_returns_by_streak.png)"),
        nbf.v4.new_markdown_cell("![首次封板时间与次日收盘收益](output/first_seal_time_scatter.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/相关系数矩阵.csv', index_col=0)"),
    ]
    nbf.write(nb, NOTEBOOK_PATH)

    print(summary_text)
    print("按首次封板时间分组")
    print(by_first_cn.to_string(index=False))
    print("\n按炸板次数分组")
    print(by_break_cn.to_string(index=False))
    print("\n按连板类型分组")
    print(by_streak_cn.to_string(index=False))
    print(f"\nNotebook: {NOTEBOOK_PATH}")
    print(f"Charts: {OUT_DIR}")


if __name__ == "__main__":
    main()
