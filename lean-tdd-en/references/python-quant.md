# Python quant test reference

> lean-tdd stack supplement. Load only when a quant/data Python project is detected.

## Detection markers

`pyproject.toml` / `requirements.txt` with vectorbt / pypfopt / akshare / baostock / pandas / numpy in dependencies → this reference applies.

## Core principle: determinism first

The biggest enemy in financial testing is "passed, but the data moved."

- **All market data comes from fixtures**: synthetic OHLCV (fixed-seed `np.random` or hand-written CSV fixtures). Never call akshare/baostock in tests — mock data sources at the boundary
- Assert time series with `pd.testing.assert_frame_equal` / `assert_series_equal`; floats with `np.isclose` / `assert_allclose` (explicit rtol/atol)
- Unify index timezones (UTC); align calendars before merging cross-source data

## Writing the RED test

```python
def test_rebalance_triggers_on_5pct_drift():
    prices = load_fixture("three_etf_2024.csv")  # synthetic deterministic data
    portfolio = RiskParityPortfolio(target_weights={"csi300": 0.41, "gold": 0.30, "nasdaq": 0.29})

    events = portfolio.rebalance_events(prices, threshold=0.05)

    assert events.iloc[0].date == pd.Timestamp("2024-03-15")
    assert events.iloc[0].asset == "gold"
```

## Quant-specific anti-patterns (append to Red Flags)

| Symptom | Likely root cause |
|---------|-------------------|
| Backtest results too good to be true | **Lookahead bias**: signal uses the T-day close but trades on T; weights leaked future data |
| In-sample vs out-of-sample cliff | Overfitting: parameters tuned on the full sample; a walk-forward test should assert OOS decay stays within bounds |
| Randomly failing tests | Seed not pinned; or dict/set iteration order leaking into results |
| NaN silently propagating | Data gaps not handled explicitly: `dropna()` swallowing the problem vs asserting gap rates |
| Weights sum ≠ 1 | Normalization at the wrong point; optimizer failure silently falling back to equal weights — failures must raise |

## Optimizer / ML tests

- pypfopt results: assert weights sum ≈ 1, no negative weights (unless shorting allowed), sign of boundary-asset weights
- sklearn pipelines: fit/transform the whole `Pipeline` once each; assert shapes and no leakage (fit on the training segment only)
- Stochastic algorithms get two test classes: (a) same seed reproduces, (b) convergence asserted against a loose interval

## Performance

- Full-history backtests do not belong in unit tests; use small-window fixtures (e.g. 60 trading days)
- Mark slow integration tests `@pytest.mark.slow`, skipped by default, run before releases
