# 涨停属性因子研究

这个轻量项目只研究“首日涨停属性”对后续收益的影响，不再纳入资金流、行业、趋势因子等其他变量。

## 研究变量

自变量：

- 涨停类型：首板、二板、三板、N板
- 第一次封板时间
- 最后封板时间
- 炸板次数
- 尾盘是否封板
- 封单金额
- 封单量
- 封单比

因变量：

- 第二日开盘收益
- 第二日最高收益
- 第二日最低收益
- 第二日收盘收益
- 第三日收益
- 是否连板

## 数据来源

默认读取上级项目已经生成的：

```text
../data/processed/model_dataset.csv
```

然后只保留本研究需要的字段，生成：

```text
data/limit_up_attribute_dataset.csv
```

注意：当前东方财富公开接口中，`封单量`、`封单比`、`尾盘是否封板`历史字段缺失较多。本项目保留这些字段，但不会强行填 0。

## 运行方式

在上级项目根目录运行：

```powershell
.\.venv311\Scripts\python.exe limit_up_attribute_study\prepare_dataset.py
.\.venv311\Scripts\python.exe limit_up_attribute_study\analyze.py
```

输出：

```text
limit_up_attribute_study/output/
```

包括：

- 数据质量报告
- 分组统计表
- 图表
- 初步结论 Markdown

