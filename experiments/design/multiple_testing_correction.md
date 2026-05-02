# Multiple-Testing Correction

Updated: 2026-05-02

Stage A intentionally tests many configurations, so raw Sharpe rankings are not enough.

Required controls:

- Track the number of completed trials per asset class.
- Track the number of completed trials per feature family and subscription family.
- Compute Sharpe, skewness, kurtosis, sample count, and drawdown per run.
- Estimate Deflated Sharpe Ratio for promoted candidates.
- Require DSR p-value below 0.01 for strong claims.
- Treat 0.01 to 0.05 as exploratory only.
- Report seed mean, seed standard deviation, and worst-seed metrics for every promoted candidate.
- Add Probability of Backtest Overfitting / CSCV-style diagnostics for Stage B where feasible.
- Add Reality Check / SPA-style family-level tests where feasible for broad feature/source families.
- Report paired uplift uncertainty, median/IQM-style aggregates, and bootstrap confidence intervals where feasible.
- Report raw ranking and multiple-testing-adjusted ranking separately.
- Never use 2025 held-out results to tune feature selection, rewards, or hyperparameters.

The Stage A summary must include both raw rankings and multiple-testing-adjusted rankings.

## PBO / CSCV Diagnostic

If implementation is feasible within Stage 3.1, Stage B must estimate overfitting risk by combinatorially symmetric cross-validation or an equivalent PBO-style diagnostic. If full CSCV is too expensive, the Stage B summary must still report:

- number of tried configurations in the comparable selection family
- selected candidate rank stability across validation folds or subperiods
- in-sample versus validation rank correlation
- worst-fold net Sharpe under base cost

Candidates with strong raw Sharpe but weak adjusted evidence are labeled exploratory and cannot be used for final claims.

## Reality Check / SPA Family Tests

For broad Stage A families, add White Reality Check or Hansen SPA-style family tests where feasible. These tests are applied at the feature/source-family level, not only at the single best run level.

Required family-test inputs:

- matched candidate returns after costs
- family id and source-family id
- asset/timeframe/algorithm/seed/split identifiers
- block or stationary bootstrap settings suitable for dependent returns

Promotion interpretation:

- A single high-Sharpe candidate with weak family-level evidence remains `watch` or `blocked`.
- Paid-source families must show marginal value versus the matched free baseline, not merely a leaderboard win.
