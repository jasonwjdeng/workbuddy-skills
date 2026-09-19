# Python quant diagnostics reference

> lean-debug stack supplement. Load when quant dependencies (vectorbt/pypfopt/akshare/pandas/numpy) are detected.

## Feedback loop construction (Phase 1, stack-preferred order)

1. Failing test: small-window fixture (60 synthetic trading days) unit test
2. CLI + fixture CSV, diffing output (weights / signals / metrics snapshot)
3. Replay captures: save real akshare/baostock responses as fixtures, replay offline
4. Interactive slicing: `to_pickle` the offending DataFrame from a REPL, recompute step by step

## Top pandas traps (first stop for Phase 3 hypotheses)

| Symptom | Likely root cause |
|---------|-------------------|
| Results are all NaN | **Index alignment**: indexes don't match in a join/op; pandas silently reindexes to an empty intersection |
| Row explosion after merge | Duplicate index + merge cartesian product; `assert df.index.is_unique` first |
| Timezone comparison errors / wrong results | naive vs aware mixing; unify with `tz_convert('UTC')` |
| Changed the df but nothing changed | `SettingWithCopyWarning`: chained assignment wrote to a copy; use `.loc` |
| Numeric column became object | A string/None slipped in, dtype silently upcast; inspect `df.dtypes` column by column |
| rolling off by one row | Wrong assumptions about `min_periods` and the `closed` parameter |

## vectorbt specifics

- `from_signals` vs `from_orders` have different semantics (signal alignment vs explicit orders) — mixing them makes results incomparable
- The `freq` parameter must match the data's true frequency; get it wrong and all annualization/holding periods are wrong
- Signal/price index off by one row = hidden lookahead or lag — assert identical indexes before calling vbt

## Numerics

- inf sources: `pct_change` hitting a zero price; assert positive prices first
- Returns off by 100×: decimal vs percentage confusion
- Covariance matrix not positive-definite → optimizer blows up: print the smallest eigenvalue before Ledoit-Wolf or eigenvalue clipping

## Performance branch (measure first)

- Slow backtest: `py-spy top --pid <pid>` on the live process; offline `cProfile` + `snakeviz`
- Memory blowup: `df.memory_usage(deep=True)` sorted by column — object columns and float64 are the prime suspects (downcast)
- Slow data loading: CSV → parquet/feather; stop re-hitting akshare (add a local cache layer)

## External data sources

- akshare/baostock schemas change silently (no version guarantee): assert the response schema in the loop (column set + minimum row count)
- Rate limiting / IP bans: exponential backoff + local cache; when diagnosing, first determine "did the API change" vs "am I throttled" (save raw responses)
