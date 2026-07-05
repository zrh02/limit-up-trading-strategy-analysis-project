from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import ATTRIBUTE_DATA, OUTPUT_DIR


RETURNS = ["第二日开盘收益", "第二日最高收益", "第二日最低收益", "第二日收盘收益", "第三日收益"]


def setup_plot():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def summarize(df, group_col):
    out = (
        df.groupby(group_col, dropna=False)
        .agg(
            样本数=("股票代码", "size"),
            第二日开盘收益均值=("第二日开盘收益", "mean"),
            第二日最高收益均值=("第二日最高收益", "mean"),
            第二日最低收益均值=("第二日最低收益", "mean"),
            第二日收盘收益均值=("第二日收盘收益", "mean"),
            第三日收益均值=("第三日收益", "mean"),
            第二日收盘上涨概率=("第二日收盘收益", lambda x: (x > 0).mean()),
            连板概率=("是否连板", "mean"),
        )
        .reset_index()
    )
    pct_cols = [col for col in out.columns if col not in [group_col, "样本数"]]
    out[pct_cols] = out[pct_cols] * 100
    return out


def plot_group(summary, group_col, title, filename):
    cols = ["第二日开盘收益均值", "第二日最高收益均值", "第二日收盘收益均值", "第三日收益均值"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(summary))
    width = 0.8 / len(cols)
    for i, col in enumerate(cols):
        ax.bar(x + i * width - 0.4 + width / 2, summary[col], width=width, label=col)
    ax.set_xticks(x)
    ax.set_xticklabels(summary[group_col].astype(str), rotation=20, ha="right")
    ax.axhline(0, color="#555", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("收益率（%）")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=160)
    plt.close(fig)


def data_quality(df):
    rows = []
    for col in df.columns:
        rows.append(
            {
                "字段": col,
                "非空数量": int(df[col].notna().sum()),
                "缺失数量": int(df[col].isna().sum()),
                "缺失率": df[col].isna().mean(),
            }
        )
    return pd.DataFrame(rows)


def main():
    setup_plot()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ATTRIBUTE_DATA, dtype={"股票代码": str}, low_memory=False)

    quality = data_quality(df)
    quality.to_csv(OUTPUT_DIR / "数据质量报告.csv", index=False, encoding="utf-8-sig")

    core_cols = ["涨停类型", "第一次封板时间", "最后封板时间", "炸板次数", *RETURNS, "是否连板"]
    core = df.dropna(subset=core_cols).copy()
    core.to_csv(OUTPUT_DIR / "可分析样本.csv", index=False, encoding="utf-8-sig")

    by_type = summarize(core, "涨停类型")
    by_time = summarize(core, "首封时间段")
    by_break = summarize(core, "炸板次数分组")

    type_order = ["首板", "二板", "三板", "N板"]
    time_order = ["09:25-09:30", "09:30-10:00", "10:00-11:30", "13:00-14:00", "14:00-15:00"]
    break_order = ["0次", "1次", "2-3次", "4次及以上"]
    by_type = by_type.set_index("涨停类型").reindex(type_order).dropna(subset=["样本数"]).reset_index()
    by_time = by_time.set_index("首封时间段").reindex(time_order).dropna(subset=["样本数"]).reset_index()
    by_break = by_break.set_index("炸板次数分组").reindex(break_order).dropna(subset=["样本数"]).reset_index()

    by_type.to_csv(OUTPUT_DIR / "按涨停类型分组.csv", index=False, encoding="utf-8-sig")
    by_time.to_csv(OUTPUT_DIR / "按第一次封板时间分组.csv", index=False, encoding="utf-8-sig")
    by_break.to_csv(OUTPUT_DIR / "按炸板次数分组.csv", index=False, encoding="utf-8-sig")

    plot_group(by_type, "涨停类型", "涨停类型与后续收益", "涨停类型与后续收益.png")
    plot_group(by_time, "首封时间段", "第一次封板时间与后续收益", "第一次封板时间与后续收益.png")
    plot_group(by_break, "炸板次数分组", "炸板次数与后续收益", "炸板次数与后续收益.png")

    conclusion = [
        "# 涨停属性影响初步结论",
        "",
        f"- 原始样本数：{len(df):,}",
        f"- 同时具备核心涨停属性和因变量的可分析样本数：{len(core):,}",
        f"- 可分析日期范围：{core['日期'].min()} 至 {core['日期'].max()}",
        "",
        "## 主要观察",
        "",
        "1. 第一次封板越早，第二日收益整体越强，尤其是 09:25-09:30 组。",
        "2. 尾盘才第一次封板的样本，第二日收盘收益和胜率明显偏弱。",
        "3. 连板高度越高，当前样本中后续收益均值越高，但三板和 N 板样本较少，需要谨慎。",
        "4. 炸板次数与收益不是简单线性关系，4次及以上组表现反而较强，可能代表强分歧后回封，需要进一步结合市场环境验证。",
        "",
        "## 数据限制",
        "",
        "- 封单量、封单比、尾盘是否封板当前缺失较多，暂不适合做可靠结论。",
        "- 当前可分析样本主要来自东方财富涨停池中有封板细节的样本，不代表全部触板股票。",
    ]
    (OUTPUT_DIR / "初步结论.md").write_text("\n".join(conclusion), encoding="utf-8")

    print(f"原始样本数: {len(df):,}")
    print(f"可分析样本数: {len(core):,}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("\n按涨停类型分组")
    print(by_type.to_string(index=False))
    print("\n按第一次封板时间分组")
    print(by_time.to_string(index=False))
    print("\n按炸板次数分组")
    print(by_break.to_string(index=False))


if __name__ == "__main__":
    main()

