# Multiple-Testing Correction

Updated: 2026-05-02

Stage A intentionally tests many configurations, so raw Sharpe rankings are not enough.

Required controls:

- Track the number of completed trials per asset class.
- Compute Sharpe, skewness, kurtosis, sample count, and drawdown per run.
- Estimate Deflated Sharpe Ratio for promoted candidates.
- Require DSR p-value below 0.01 for strong claims.
- Treat 0.01 to 0.05 as exploratory only.
- Never use 2025 held-out results to tune feature selection, rewards, or hyperparameters.

The Stage A summary must include both raw rankings and multiple-testing-adjusted rankings.
