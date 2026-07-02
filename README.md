# A 股主板打板策略定量研究框架

本项目用于研究 2025-06-01 至 2026-06-30 A 股主板“当日最高价触及涨停价”的股票样本，覆盖封住涨停和盘中炸板两类样本。代码优先使用东方财富公开接口，并保留缓存、限速、重试、日志、清洗和特征工程流程。

## 目录结构

```text
.
├── crawler/                  # 数据采集模块
├── feature_engineering/      # 趋势因子、因变量、宽表合并
├── analysis/                 # 后续研究脚本/Notebook
├── data/
│   ├── raw/                  # 原始接口数据与 HTTP 缓存
│   ├── cleaned/              # 清洗后的中间表
│   └── processed/            # 最终建模宽表
├── config.py
├── main.py
├── utils.py
├── data_dictionary.csv
└── requirements.txt
```

## 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 一键运行

```bash
python main.py
```

常用参数：

```bash
python main.py --start-date 2025-06-01 --end-date 2026-06-30
python main.py --force        # 忽略本地 CSV 缓存，重新抓取和计算
python main.py --skip-crawl   # 使用 data/cleaned 里的已有数据，仅重建特征和宽表
```

最终输出：

```text
data/processed/model_dataset.csv
```

## 数据源与字段

字段字典见 `data_dictionary.csv`，包括中文含义、英文字段名、类型、来源和计算方法。

主要模块：

- `crawler/daily.py`：东方财富日 K，获取 open、high、low、close、volume、amount、turnover_rate。
- `crawler/limit_up.py`：东方财富涨停池，并用日线估算补充“最高价触及涨停但未封板”的炸板样本。
- `crawler/basic.py`：股票名称、市值、PE、PB、上市日期，并计算上市天数。
- `crawler/money_flow.py`：资金流字段，金额统一转为亿元，比例统一转为小数。
- `crawler/sector.py`：保留行业/概念特征字段。东方财富历史行业和概念归属接口公开稳定性较弱，严格研究建议替换为 AkShare、Tushare 或每日沉淀快照。
- `crawler/market.py`：上证指数、深证成指涨跌幅，以及由样本统计出的全市场涨停家数和炸板率。
- `feature_engineering/trend_factor.py`：近 5/10/20 日涨幅、成交量变化、60 日新高、连续上涨/阳线。
- `feature_engineering/target.py`：次日开盘/最高/最低/收盘收益、第三日收益、是否连板。

## 清洗规则

- 股票代码统一为 6 位字符串。
- 日期统一为 `YYYY-MM-DD`。
- 金额字段统一为亿元，原始日行情 `amount` 暂保留东方财富接口原单位，资金流和市值字段已转亿元。
- 比例字段统一为小数，例如 `5%` 存为 `0.05`。
- 封板时间统一为 `HH:MM:SS`。
- 缺失值保留为 `NaN`，不随意填 0。
- 所有股票日度表按 `date + code` 合并。
- PE、PB、市值等极端值可用 `utils.winsorize_df()` 或 `utils.winsorize_series()` 做可选缩尾处理。

## 数据质量检查建议

运行完成后建议检查：

```python
import pandas as pd

df = pd.read_csv("data/processed/model_dataset.csv", dtype={"code": str})
print(df.shape)
print(df[["date", "code"]].duplicated().sum())
print(df.isna().mean().sort_values(ascending=False).head(30))
print(df["code"].str.len().value_counts())
print(df.groupby("date")["code"].nunique().describe())
```

重点关注：

- `date + code` 是否唯一。
- `is_broken` 和 `is_sealed` 是否符合研究定义。
- `next_*_return` 是否因为尾部日期缺少未来行情而为空。
- 行业/概念字段是否为空；若为空，按 TODO 替换为 AkShare/Tushare 或自有板块数据。
- 东方财富涨停池接口字段是否变化；若字段变化，优先在 `crawler/limit_up.py` 中更新字段映射。

## 重要 TODO

- 主板涨停价估算默认使用 `pre_close * 1.10` 后四舍五入，ST、新股、复牌等特殊情形已通过样本过滤尽量规避，但严格研究仍建议使用交易所涨跌停价表校验。
- 封单量、封单比、委比、尾盘是否封板等盘口字段，东方财富公开接口不保证历史稳定返回。可替代方案包括 AkShare 涨停池、Tushare、交易软件手动导出、Level-2 或逐笔盘口数据自行计算。
- 历史行业/概念归属建议用可回溯数据源补齐，否则概念特征会保留为 `NaN`。
