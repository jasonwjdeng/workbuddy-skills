# Quant investing domain question bank

> lean-design domain supplement. When a quant project is detected (vectorbt/pypfopt/akshare etc.), use the following as candidate frontier questions during batch clarification — pick what fits the task, don't ask all; still attach your recommended answer to each.

## Strategy and portfolio

- Optimization method: MVO / min-variance / risk parity / equal weight? (Recommend: risk parity — most robust to estimation error; MVO is extremely sensitive to expected-return assumptions)
- Constraints: weight bounds? Shorting allowed? Per-asset cap? (Recommend: 0-60%, no shorting)
- Benchmark and metrics: Sharpe / Calmar / max drawdown / CAGR? Benchmark against what?
- Estimation windows and methods for expected returns and covariance? (Recommend: Ledoit-Wolf shrinkage for covariance; avoid point estimates for expected returns)

## Backtesting and validation

- In-sample / out-of-sample split? Walk-forward windows (rolling vs expanding, length, step)?
- Overfitting budget: how many parameters may be tuned? Acceptable OOS decay? (Recommend: Sharpe decay < 50%)
- Fill assumptions: price (next open?), slippage, fees, minimum trade size?
- Universe point-in-timeness: is the constituent list historical or today's? (Guard against survivorship bias)

## Rebalancing

- Calendar trigger (monthly/quarterly), drift threshold (5%), or dual-trigger?
- Partial rebalancing (only back within threshold) or full reset to target?
- How are transaction costs priced into the decision?

## Data pipeline

- Primary source and fallback chain: akshare → baostock → cache? Gap policy (forward-fill cap / hard error)?
- Adjustment convention: forward-adjusted for returns, unadjusted for signals? Unified at which layer?
- Timezones and trading calendars: where do cross-market assets get aligned? (Recommend: UTC + per-market calendar join)

## Numerics and engineering

- Money precision policy: Decimal, or float + tolerance? Converted at which layer?
- Result caching and invalidation: what keys a backtest cache entry (data version + parameter hash)?
- Failure semantics: optimizer non-convergence / data gap over threshold — raise, fall back, or skip? (Recommend: raise explicitly + annotate the report)
