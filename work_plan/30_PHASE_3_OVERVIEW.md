# Phase 3 Overview - Weekly Walk-Forward Experiments

Date: 2026-06-04
Status: ACTIVE

## Active Framing

Phase 3 evaluates the business process we intend to run:

```text
weekend retrain/update -> trade next week only -> aggregate many weekly anchors
```

It does not evaluate whether one unoptimized model can trade unchanged for a
year. It also does not use short-window smoke runs as profit evidence.

## Current Canonical Documents

- `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
- `PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md`
- `31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md`
- `32_STAGE_3_2_RESULTS_SYNTHESIS.md`
- `PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md`

## Phase 3 Goal

Find data, feature, preprocessing, model-hyperparameter, and later portfolio
allocation choices that improve repeated next-week profit/risk after costs.

The main searched object is the complete candidate configuration:

- target asset;
- timeframe;
- input asset mask;
- source/data mask;
- feature family and feature subset;
- preprocessing profile;
- market-state representation;
- event-calendar risk overlay;
- model family and hyperparameters;
- training policy;
- training-window length;
- broker/cost profile.

## Required Evaluation Unit

Each candidate job is evaluated over many weekly subjobs.

```text
subjob train      = N years before validation week
subjob validation = 7 days
subjob test       = next 7 days
```

Initial sweep:

```text
train_years = 1..10
validation_days = 7
test_days = 7
training_policy = scratch_n_years
```

The previous short-window line is deleted and not active.

## Infrastructure Target

Phase 3 now requires:

- SQLite job/subjob/result pool;
- autonomous workers on local, Dragon, and Gamma;
- atomic job claiming;
- machine heartbeats;
- result/evidence storage for reproducibility;
- AdminLTE status dashboard on `http://127.0.0.1:8787`;
- OLAP-style result aggregation by asset, timeframe, training window, feature
  set, preprocessing profile, and hyperparameters.

## Stage C Rule

Stage C remains locked:

```text
heldout boundary = 2025-01-01
stage_c_access = DENIED
```

No active Phase 3 pool job may use rows on or after the heldout boundary.

## Phase 3 Stages

| Stage | Purpose |
| --- | --- |
| 3.1 | Build and run weekly walk-forward pool experiments |
| 3.2 | Aggregate weekly and portfolio evidence |
| 3.C | One-shot final heldout only after explicit approval |
