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
        return "0"
    if x == 1:
        return "1"
    if x <= 3:
        return "2-3"
    return "4+"


def bucket_streak(x):
    if pd.isna(x):
        return np.nan
    x = int(x)
    if x == 1:
        return "1st board"
    if x == 2:
        return "2nd board"
    return "3rd+ board"


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


def bar_chart(summary, x_col, y_cols, title, output):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(summary))
    width = 0.8 / len(y_cols)
    for i, col in enumerate(y_cols):
        ax.bar(x + i * width - 0.4 + width / 2, summary[col], width=width, label=col)
    ax.set_xticks(x)
    ax.set_xticklabels(summary[x_col].astype(str), rotation=20, ha="right")
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("Return / rate (%)")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def scatter_chart(df, output):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(df["first_seal_minutes"], pct(df["next_close_return"]), s=18, alpha=0.45)
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title("First seal time vs next-day close return")
    ax.set_xlabel("First seal time, minutes after 09:30")
    ax.set_ylabel("Next-day close return (%)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main():
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
    break_order = ["0", "1", "2-3", "4+"]
    streak_order = ["1st board", "2nd board", "3rd+ board"]

    by_first = summarize(core, "first_seal_bucket").set_index("first_seal_bucket").loc[first_order].reset_index()
    by_break = summarize(core, "break_count_bucket").set_index("break_count_bucket").loc[break_order].reset_index()
    by_streak = summarize(core, "streak_bucket").set_index("streak_bucket").loc[streak_order].reset_index()

    by_first.to_csv(OUT_DIR / "by_first_seal_time.csv", index=False, encoding="utf-8-sig")
    by_break.to_csv(OUT_DIR / "by_break_count.csv", index=False, encoding="utf-8-sig")
    by_streak.to_csv(OUT_DIR / "by_limit_up_streak.csv", index=False, encoding="utf-8-sig")

    bar_chart(
        by_first,
        "first_seal_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "Next-day returns by first seal time",
        OUT_DIR / "next_returns_by_first_seal_time.png",
    )
    bar_chart(
        by_break,
        "break_count_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "Next-day returns by break-seal count",
        OUT_DIR / "next_returns_by_break_count.png",
    )
    bar_chart(
        by_streak,
        "streak_bucket",
        ["next_open_mean", "next_high_mean", "next_close_mean"],
        "Next-day returns by board streak",
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
    correlations.to_csv(OUT_DIR / "correlations.csv", encoding="utf-8-sig")

    summary_text = f"""
Data scope:
- Full model dataset rows: {len(df):,}
- Rows with complete seal-detail fields and next-day returns: {len(core):,}
- Date range: {core['date'].min()} to {core['date'].max()}

Headline averages on usable seal-detail sample:
- Next open return: {pct(core['next_open_return'].mean()):.2f}%
- Next high return: {pct(core['next_high_return'].mean()):.2f}%
- Next close return: {pct(core['next_close_return'].mean()):.2f}%
- Next close win rate: {(core['next_close_return'] > 0).mean() * 100:.2f}%
"""

    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Limit-up seal-detail effect analysis\n\n"
            "This notebook analyzes whether first-day seal details are associated with next-day returns. "
            "Scope is restricted to samples with available Eastmoney limit-up pool seal-detail fields."
        ),
        nbf.v4.new_markdown_cell(summary_text),
        nbf.v4.new_code_cell(
            "import pandas as pd\n"
            "df = pd.read_csv('../data/processed/model_dataset.csv', dtype={'code': str}, low_memory=False)\n"
            "df.shape"
        ),
        nbf.v4.new_code_cell(
            "by_first = pd.read_csv('output/by_first_seal_time.csv')\n"
            "by_first"
        ),
        nbf.v4.new_markdown_cell("![Next-day returns by first seal time](output/next_returns_by_first_seal_time.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/by_break_count.csv')"),
        nbf.v4.new_markdown_cell("![Next-day returns by break count](output/next_returns_by_break_count.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/by_limit_up_streak.csv')"),
        nbf.v4.new_markdown_cell("![Next-day returns by board streak](output/next_returns_by_streak.png)"),
        nbf.v4.new_markdown_cell("![First seal time scatter](output/first_seal_time_scatter.png)"),
        nbf.v4.new_code_cell("pd.read_csv('output/correlations.csv', index_col=0)"),
    ]
    nbf.write(nb, NOTEBOOK_PATH)

    print(summary_text)
    print("By first seal time")
    print(by_first.to_string(index=False))
    print("\nBy break count")
    print(by_break.to_string(index=False))
    print("\nBy board streak")
    print(by_streak.to_string(index=False))
    print(f"\nNotebook: {NOTEBOOK_PATH}")
    print(f"Charts: {OUT_DIR}")


if __name__ == "__main__":
    main()
