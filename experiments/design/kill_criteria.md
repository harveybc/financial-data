# Project 3 Kill Criteria

Updated: 2026-05-02

Kill a Stage A configuration if any condition holds:

- Mean validation Sharpe across seeds is below 0.
- Mean validation Sharpe is within +/- 0.1 of the matching buy-and-hold or cash baseline.
- Validation max drawdown exceeds 30%.
- Training produces NaN losses, invalid actions, or unstable equity curves.
- Turnover is implausibly high after transaction costs.
- A feature preset leaks future data or uses held-out 2025 statistics.
- Gross performance is positive but net performance is non-positive under the base cost scenario.
- The candidate is dominated by a simple baseline after costs and no explicit exception is documented.
- Required availability/vintage/staleness metadata is missing for a cross-source feature family.
- A fitted transform used by the candidate fails the leakage audit.
- The candidate's edge appears only in one seed or one isolated subperiod.

Kill a Stage B configuration if:

- Mean validation Sharpe is below 0.3.
- Deflated Sharpe p-value fails the pre-registered threshold.
- Performance is driven by one seed only.
- The strategy fails basic anomaly review of trades, positions, and reward attribution.
- PBO/CSCV-style diagnostics indicate high backtest-overfitting risk, where feasible.
- The candidate fails the pessimistic cost scenario without a documented risk exception.
- Regime-sliced diagnostics show unacceptable concentrated failure.
- The candidate list, feature set, or transforms changed after Stage B validation began.

Kill a Stage C claim if:

- Held-out 2025 was evaluated more than once after seeing results.
- Any candidate was modified after held-out evaluation began.
- The final report omits losing candidates or cost-sensitivity failures.
- The result depends on research-only final-revised data while making a live-tradability claim.
