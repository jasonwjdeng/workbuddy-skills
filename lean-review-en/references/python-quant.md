# Python quant review checklist

> lean-review stack supplement. Load when pyproject/requirements includes vectorbt/pypfopt/akshare/pandas/numpy.
> Pre-graded severity: ⚠️ = usually Critical, ◆ = usually Major, · = Minor.

## Backtest correctness (highest-risk zone)

- ⚠️ **Lookahead bias**: T-day signals using T-day-or-later data (shift alignment, rolling window edges, future functions)
- ⚠️ Unrealistic fills: trading at the signal day's close, no slippage/fees, infinite liquidity
- ⚠️ Survivorship bias: universe/ETF list uses today's constituents, not the historical point-in-time set
- ◆ Rebalancing logic drifted from the declared period/threshold
- ◆ Weight normalization at the wrong point; optimizer failure silently falling back (must raise or log explicitly)

## Data pipeline

- ⚠️ Real data-source calls (akshare/baostock) mixed into the computation core — untestable, uncacheable
- ◆ Merging multi-source data without aligning timezones/calendars (A-share vs US trading days differ)
- ◆ Implicit NaN handling: `dropna()`/`fillna(0)` swallowing data-quality issues — assert gap rates
- ◆ Mixed adjustment conventions (forward/backward/unadjusted prices in one computation)
- · Data cache without an invalidation policy (stale data used silently)

## Numerics

- ⚠️ Money accumulated in float (use Decimal or an explicit precision policy)
- ◆ Division without zero guards (zero volatility, zero position)
- ◆ Return conventions mixed (simple vs log); hardcoded 252 annualization regardless of market
- · Float equality assertions (use np.isclose)

## Optimization / ML

- ⚠️ Parameters tuned on the full sample, then claimed out-of-sample (overfitting; require walk-forward assertions)
- ◆ sklearn Pipeline fitted before the train/test split (leakage)
- ◆ Stochastic algorithms without pinned seeds — irreproducible results
- · Optimization constraints (weight bounds, shorting) documented but not enforced in code

## Tests

- ◆ Tests calling real data sources (should be fixtures/mocks)
- ◆ Non-determinism: random data without seeds, unfrozen time dependencies
- · Full-history backtests inside unit tests (use small windows + slow markers)
