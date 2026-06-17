# Stage 3.1 - Weekly Walk-Forward Experiment Framework

Date: 2026-06-04
Status: ACTIVE

## Purpose

Stage 3.1 builds the experiment machinery for Project 3's real business loop:
weekly retraining or updating, next-week trading, and aggregation across many
historical weekly anchors.

## Candidate Job Contract

Each job must define:

```text
job_id
target_asset
timeframe
input_asset_mask
input_source_mask
feature_preset
feature_selection_method
selected_features
preprocessing_profile
market_state_profile_id
model_family
agent_plugin
env_plugin
pipeline_plugin
training_policy
train_years
early_stop_train_tail_days
validation_days
test_days
hyperparameters
broker_profile
cost_scenario
stage_c_access
```

Initial serious sweep:

```text
target_asset = btcusdt_perp first
timeframe = 4h first
model_family = SAC actor-critic first
training_policy = scratch_n_years
train_years = 1..10
early_stop_train_tail_days = 7 first, then 14/28 comparison
validation_days = 7 first, then 14/28 comparison
test_days = 7 first, then 14/28 comparison
seeds = 0,1,2
```

## Subjob Contract

Each job expands into weekly anchor subjobs:

```text
weekly_anchor_id
train_start
train_end
validation_start
validation_end
test_start
test_end
train_rows
validation_rows
test_rows
machine assignment/claim status
config path
run path
evidence path
result metrics
```

The subjob is the actual unit claimed by a machine. The job score is the
aggregate of all subjobs.

## Training Policies

Support three families, but implement in this order:

1. `scratch_n_years`: train from scratch for every weekly anchor.
2. `warm_start_4y_then_1y`: train initial model on 4 years, then weekly
   fine-tune with last 1 year plus optional replay.
3. `warm_start_4y_light`: train initial model on 4 years, then light weekly
   updates with the same 4-year window.

Do not compare a warm-start score directly against a scratch score without
labeling the family.

## Validity Rules

Hard failures:

- any row on or after `2025-01-01`;
- missing data file or hash;
- missing feature list;
- impossible split ordering;
- too few rows in train/validation/test;
- missing result/evidence file;
- impossible accounting;
- broker hard-limit violation.

Not hard failures:

- one negative week;
- one weak seed;
- poor return during early search.

Those are optimizer feedback, not reasons to stop the experiment framework.

## Required Implementation

Use:

```text
PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md
```

The first code milestone is:

- SQLite job pool;
- weekly split/config materializer;
- worker loop for local/Dragon/Gamma;
- AdminLTE dashboard;
- seed plan worker in `financial-data`.

## User Gate

Before broad runs, show:

- dashboard URL;
- DB path;
- seed plan summary;
- queue counts;
- first tiny mechanical result;
- proof that Stage C is denied.
