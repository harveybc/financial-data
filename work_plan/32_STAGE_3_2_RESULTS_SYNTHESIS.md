# Stage 3.2 - Weekly Walk-Forward Results Synthesis

Date: 2026-06-04
Status: ACTIVE

## Purpose

Stage 3.2 aggregates weekly walk-forward pool results. A result is meaningful
only after repeated weekly anchors, not after one short smoke run.

## Source Of Truth

Primary source:

```text
financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

The database stores jobs, subjobs, machine heartbeats, artifacts, and results.
File artifacts are referenced by the DB for reproducibility.

## Required Aggregations

Aggregate by:

- target asset;
- timeframe;
- training policy;
- train_years;
- feature preset;
- feature selection method;
- preprocessing profile;
- market-state profile;
- hyperparameter family;
- seed;
- cost scenario;
- broker profile.

## Required Metrics

Per job:

- completed subjob count;
- failed subjob count;
- mean, median, and IQM test return;
- positive test-week rate;
- validation/test return correlation;
- test Sharpe;
- downside Sharpe;
- max drawdown;
- CVaR;
- test trades/week;
- cost-to-gross-edge ratio;
- action entropy and action balance;
- broker/Friday violation count;
- seed stability.

## Required Leaderboards

- best by mean test return;
- best by median/IQM test return;
- best by risk-adjusted return;
- best by low drawdown/CVaR;
- best by train_years;
- best feature/preprocessing combination;
- best model hyperparameter region;
- worst/fragile candidates to kill.

## Required Reports

```text
weekly_walkforward_summary.md
training_window_sweep.md
feature_preprocessing_value_ranking.md
hyperparameter_value_ranking.md
asset_input_value_ranking.md
failure_and_blocker_report.md
reproducibility_index.md
```

## Interpretation Rules

- A single profitable week proves nothing.
- A single unprofitable week kills nothing.
- A candidate becomes interesting when it improves repeated next-week
  profit/risk across anchors, seeds, and costs.
- Stage C remains untouched until explicitly approved.
