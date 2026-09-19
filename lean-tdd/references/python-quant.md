# Python 量化测试参考

> lean-tdd 的技术栈补充。仅在检测到量化/数据类 Python 项目时加载。

## 检测标记

`pyproject.toml` / `requirements.txt` + 依赖中出现 vectorbt / pypfopt / akshare / baostock / pandas / numpy → 本参考生效。

## 核心原则：确定性优先

金融测试最大的敌人是"看起来过了其实数据变了"。

- **行情数据一律用 fixture**：合成 OHLCV（固定 seed 的 `np.random` 或手写的 CSV fixture），测试里禁止真实调用 akshare/baostock——数据源 mock 在边界上
- 时间序列断言用 `pd.testing.assert_frame_equal` / `assert_series_equal`，浮点用 `np.isclose` / `assert_allclose`（明确 rtol/atol）
- 索引时区统一（UTC），跨源数据合并前先对齐日历

## RED 的写法

```python
def test_rebalance_triggers_on_5pct_drift():
    prices = load_fixture("three_etf_2024.csv")  # 合成确定性数据
    portfolio = RiskParityPortfolio(target_weights={"csi300": 0.41, "gold": 0.30, "nasdaq": 0.29})

    events = portfolio.rebalance_events(prices, threshold=0.05)

    assert events.iloc[0].date == pd.Timestamp("2024-03-15")
    assert events.iloc[0].asset == "gold"
```

## 量化特有的反模式（Red Flags 追加）

| 症状 | 根因方向 |
|------|----------|
| 回测结果好得离谱 | **前视偏差**：信号用了 T 日收盘价却在 T 日成交；权重计算泄漏了未来数据 |
| 样本内/外表现断崖 | 过拟合：参数在全样本上调优；应有 walk-forward 测试断言 OOS 衰减在可接受范围 |
| 测试随机挂 | 没钉 seed；或字典/集合迭代序影响结果 |
| NaN 悄悄传播 | 数据缺口没显式处理：`dropna()` 吞掉问题 vs 显式断言缺口率 |
| 权重和 ≠ 1 | 归一化时机错误；优化器失败时静默回退等权——失败要显式抛出 |

## 优化器/ML 测试

- pypfopt 优化结果：断言权重和≈1、无负权重（除非允许做空）、边界资产权重的符号
- sklearn 管线：`Pipeline` 整体 fit/transform 各跑一次，断言形状与无泄漏（fit 只用训练段）
- 随机算法（种子树/优化迭代）测试两类：(a) 同 seed 可复现 (b) 收敛断言放宽松区间

## 性能

- 全量历史回测不进单元测试；用小窗口 fixture（如 60 个交易日）
- 慢集成测试标 `@pytest.mark.slow`，默认跳过，发版前跑
