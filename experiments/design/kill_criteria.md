# Project 3 Kill Criteria

Updated: 2026-05-02

Kill a Stage A configuration if any condition holds:

- Mean validation Sharpe across seeds is below 0.
- Mean validation Sharpe is within +/- 0.1 of the matching buy-and-hold or cash baseline.
- Validation max drawdown exceeds 30%.
- Training produces NaN losses, invalid actions, or unstable equity curves.
- Turnover is implausibly high after transaction costs.
- A feature preset leaks future data or uses held-out 2025 statistics.

Kill a Stage B configuration if:

- Mean validation Sharpe is below 0.3.
- Deflated Sharpe p-value fails the pre-registered threshold.
- Performance is driven by one seed only.
- The strategy fails basic anomaly review of trades, positions, and reward attribution.
