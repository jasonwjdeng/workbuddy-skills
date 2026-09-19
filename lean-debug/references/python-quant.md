# Python 量化诊断参考

> lean-debug 的技术栈补充。检测到 quant 依赖（vectorbt/pypfopt/akshare/pandas/numpy）时加载。

## 反馈回路构造（Phase 1，栈内优先序）

1. 失败测试：小窗口 fixture（60 个交易日合成数据）单测
2. CLI + fixture CSV，diff 输出（权重/信号/指标快照）
3. 重放捕获：把真实 akshare/baostock 响应存成 fixture，离线重放复现
4. 交互式切片：REPL 里把出问题的 DataFrame `to_pickle` 存下来，单步重算

## pandas 高频坑（Phase 3 假设清单首选）

| 症状 | 根因方向 |
|------|---------|
| 结果全是 NaN | **索引对齐**：两表 join/运算时索引不匹配，pandas 静默 reindex 出空交集 |
| 合并后行数爆炸 | 重复索引 + merge 笛卡尔积；先 `assert df.index.is_unique` |
| 时区比较报错/结果错 | naive vs aware 混用；统一 `tz_convert('UTC')` |
| 改了 df 但结果没变 | `SettingWithCopyWarning`：链式赋值改的是副本；用 `.loc` |
| 数值变 object | 某列混入字符串/None，dtype 被静默升级；`df.dtypes` 逐列看 |
| rolling 结果差一行 | 窗口边界 `min_periods` 与 closed 参数假设错误 |

## vectorbt 特定

- `from_signals` vs `from_orders` 语义不同（信号对齐 vs 显式订单），混用结果对不上
- `freq` 参数必须与数据真实频率一致，错了整个年化/持仓期都错
- 信号与价格索引错位一行 = 隐性前视或滞后——用 `vbt` 前先断言两者索引 identical

## 数值问题

- inf 来源：`pct_change` 遇到 0 价格；先断言价格正数
- 收益率量级差 100 倍：小数 vs 百分数混用
- 协方差矩阵非正定 → 优化器炸：Ledoit-Wolf 或特征值截断前先打印最小特征值确认

## 性能分支（先量后改）

- 慢回测：`py-spy top --pid <pid>` 看活进程火焰；离线用 `cProfile` + `snakeviz`
- 内存爆：`df.memory_usage(deep=True)` 按列排序，object 列和 float64 是主要嫌疑（downcast）
- 数据加载慢：CSV → parquet/feather；不要反复读 akshare（加本地缓存层）

## 外部数据源

- akshare/baostock 接口字段会静默变更（无版本保证）：回路里断言响应 schema（列名集合 + 行数下限）
- 限流/封 IP：指数退避 + 本地缓存，排障时先确认是"接口变了"还是"被限流了"（保存原始响应）
