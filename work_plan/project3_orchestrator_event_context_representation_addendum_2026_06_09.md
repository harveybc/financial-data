# Project 3 Event-Context Representation Addendum

Date: 2026-06-09
Status: ACTIVE PRAGMATIC ADDENDUM

## Decision

Add event/calendar/news context to Project 3, but not as a separate academic
stage that blocks progress. Treat it as a new family of candidate inputs inside
the weekly retrained walk-forward pool.

The first goal is not to build an LLM trader. The first goal is to test whether
point-in-time event context improves the weekly production loop:

```text
train/update before cutoff -> validate next week -> inspect test week ->
repeat across weekly anchors -> rank by aggregated train-tail + validation
```

The event-context work must help us choose better data, risk overlays, no-trade
windows, sizing decisions, and eventually model observations. It must not become
another pile of gates that delays useful experimentation.

## Business Reality

Project 3 is a weekly retrained trading system. The business assumption is:

- models are retrained or updated every weekend;
- models only need to behave well in the following trading week;
- selection must be based on repeated historical weekly anchors;
- the final product is a portfolio/trading service, not an academic benchmark;
- profit/risk after realistic costs matters more than elegant methodology.

Therefore event context is useful only if it improves one or more of:

- average weekly train-tail + validation score;
- test-week behavior of candidates selected by train-tail + validation;
- drawdown/CVaR around high-risk event windows;
- no-trade/sizing decisions;
- stability across weekly anchors, assets, and training policies.

## Current Evidence Context

The active pool uses:

```text
score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

The test split is reported for the candidate selected by train-tail +
validation, but test must not be used as the selection criterion.

Recent pool evidence showed:

- BTC-perp/SAC with current `sota_low_cost` features did not produce positive
  composite scores.
- The multi-asset sweep found preliminary positive composite candidates on
  `ethusdt` 4h.
- This suggests the next useful question is not "can a fancier stage pass?"
  but "which asset/data/context combinations improve the weekly score?"

Event context should therefore be tested first on promising assets such as
`ethusdt` 4h, and later on FX assets where scheduled macro events are more
directly relevant.

## What Event Context Means Here

Event context means point-in-time information known before each model decision.
It can include:

- scheduled future economic events;
- country/currency/event-family metadata;
- provider importance;
- consensus forecast if available before the decision cutoff;
- time until event;
- event clustering in the next 24/72/168 hours;
- actual-vs-forecast surprise only after the result is actually available;
- revised values only after the revision is available;
- geopolitical/news risk signals when timestamped and auditable;
- cross-asset and market-state context already in our data inventory.

The key timestamp rule is:

```text
active_event_field_allowed = first_available_ts <= model_decision_ts
```

If `first_available_ts` is missing for actual/forecast/revision/surprise fields,
those fields cannot enter model observations. They may be used only for source
coverage reporting.

## First Implementation Target

Do not start with a transformer. Start with engineered event features that can
be joined into the weekly pool input files and compared directly against the
current baseline.

First profile family:

```text
event_engineered_summary_v1
```

Candidate columns:

```text
event_upcoming_high_count_24h
event_upcoming_high_count_72h
event_upcoming_high_count_168h
event_min_hours_to_high_impact
event_sum_importance_weighted_relevance_24h
event_sum_importance_weighted_relevance_168h
event_cluster_count_6h
event_cluster_count_12h
event_cluster_count_24h
event_cpi_week_flag
event_nfp_week_flag
event_fomc_week_flag
event_central_bank_week_flag
event_time_since_last_high_impact_hours
event_recent_abs_surprise_z_max_24h
event_recent_signed_surprise_z_sum_24h
event_no_trade_window_active
event_spread_stress_multiplier
event_slippage_stress_multiplier
```

Surprise fields are allowed only when first-available timestamps prove they
were known at the decision time.

## Evaluation Design

Every event-context experiment must be paired against a matched baseline.

Example:

```text
baseline:
  asset: ethusdt
  timeframe: 4h
  feature_preset: sota_low_cost
  model: SAC
  training_policy: scratch_n_years / warm_start_chain_n_years
  anchors: same weekly anchors

event candidate:
  same as baseline
  feature_preset: sota_low_cost_plus_event_engineered_v1
```

The candidate wins only if the repeated weekly aggregate improves:

```text
primary_score = mean_over_subjobs(
  0.5 * train_tail_total_return + 0.5 * validation_total_return
)
```

Secondary diagnostics:

- selected-candidate test return;
- test Sharpe;
- drawdown/CVaR if available;
- trades per week;
- event-window return/drawdown;
- no-trade coverage;
- cost/slippage stress;
- whether benefit comes from useful selectivity or simply going flat.

No single positive week is enough. A one-week positive result is a clue, not a
promotion.

## Order Of Work

### Implementation Status As Of 2026-06-09

Implemented:

- `project3_event_context_source_coverage_worker.py` audits source coverage and
  timestamp semantics.
- `project3_event_engineered_feature_builder.py` builds
  `event_engineered_summary_v1` scheduled/context features.
- `project3_weekly_pool_plan_worker.py` now preserves optional `event_*`
  feature columns and includes `feature_preset` in subjob ids so matched
  baseline and event-context jobs can coexist in SQLite.
- `project3_weekly_pool_enqueue_plan.py` enqueues weekly pool plans
  idempotently.

First real candidate generated and enqueued:

```text
asset: ethusdt
timeframe: 4h
baseline preset: sota_low_cost
candidate preset: sota_low_cost_plus_event_engineered_v1
policies: scratch_n_years, warm_start_chain_n_years
train_years: 1
anchors: 8
subjobs: 16
feature_count: 40
```

Current event-data limitation:

```text
first_available_ts is missing for actual/forecast/revision/surprise sources.
Therefore actual/surprise fields are disabled in trading observations until a
provider or reconstruction path supplies point-in-time availability timestamps.
```

### E0: Source Coverage Audit

Find what historical event/calendar/news data we actually have.

Required output:

```text
experiments/stage3x_event_context/event_source_coverage_report.json
```

Questions to answer:

- Which providers/sources exist?
- Which assets/currencies/event families are covered?
- Do we have scheduled release timestamps?
- Do we have forecast values?
- Do we have actual values?
- Do we have previous/revised values?
- Do we have first-available or ingest timestamps?
- What is the coverage start/end?
- Can the source support weekly rolling validation before 2025-01-01?

If timestamp semantics are unknown, stop at E0 for actual/surprise features.

### E1: Engineered Event Feature Builder

Build deterministic event features with point-in-time masking.

Required output:

```text
experiments/stage3x_event_context/event_engineered_summary_v1.json
experiments/stage3x_event_context/event_feature_availability_audit.json
```

This is CPU work. No GPU training is required.

### E2: Join Into Candidate Input Files

Create new input CSVs such as:

```text
experiments/stage_a_screening/inputs/ethusdt/4h/sota_low_cost_plus_event_v1/train.csv
```

The join must preserve:

- row count;
- row order;
- `DATE_TIME`;
- no Stage C rows;
- source hash;
- event profile hash.

### E3: Weekly Pool Comparison

Enqueue paired baseline-vs-event candidates into the SQLite weekly pool.

The first comparison should use:

```text
asset: ethusdt
timeframe: 4h
policies: scratch,warm_start_chain
train_years: 1,3,4
metric windows: 7/7/7 first
```

FX assets may follow after source coverage is verified because event context is
especially relevant there.

### E4: Variable-Length Event Tokens

Only after engineered features are proven useful or diagnostically important,
create a token representation:

```text
one event = one token
token MLP -> attention pooling -> fixed event embedding
```

This is the first "LLM-like" architecture, but it is not a generative LLM. It
is a compact encoder for irregular event sets.

### E5: Larger Attention Architectures

Only after E4 has evidence, test:

- Set Transformer;
- time-aware transformer;
- Temporal Fusion Transformer-style known-future/observed-past fusion;
- Perceiver-style bottleneck if token count becomes large.

These are not first-step implementations.

## LLM Policy

Allowed LLM use:

- normalize event names;
- classify event family;
- map news to countries/currencies/assets;
- extract geopolitical event labels;
- assist research review.

Forbidden initial LLM use:

- direct trading decisions;
- direct portfolio allocation;
- unverified event facts;
- features without deterministic source timestamps;
- any output that cannot be audited and hashed.

LLM-derived labels must be converted into deterministic structured fields and
validated against timestamped source metadata before entering experiments.

## Practical Go/No-Go Rules

These rules are pragmatic controls, not stage barriers:

- If event data lacks reliable timestamps, use only scheduled-event risk
  features and block actual/surprise fields.
- If engineered event features do not improve the weekly pool or risk
  diagnostics, do not build learned event encoders yet.
- If improvement comes only from zero trades, mark the feature as risk-overlay
  only, not alpha.
- If event features improve train-tail + validation but test collapses
  repeatedly, treat it as overfit and move to more anchors/assets.
- If event features improve `ethusdt`, test whether the effect generalizes to
  other crypto and FX assets before allocating big GPU time.
- Keep Stage C denied until final locked evaluation.

## Required Artifacts

Use:

```text
experiments/stage3x_event_context/
```

Minimum artifacts:

```text
event_source_coverage_report.json
event_feature_availability_audit.json
event_engineered_summary_v1.json
event_context_join_report.json
event_context_weekly_pool_plan.json
event_context_weekly_pool_synthesis.md
```

Later artifacts:

```text
event_token_contract.json
event_token_set_encoder_v1.json
selected_event_context_profiles.json
```

## Research Questions For The Next Iteration

1. Does `sota_low_cost_plus_event_v1` improve `ethusdt` 4h over the current
   `sota_low_cost` baseline?
2. Are improvements concentrated around high-impact event weeks?
3. Does the feature help by increasing return, reducing drawdown, reducing bad
   exposure, or simply suppressing trades?
4. Is the effect stronger on FX than crypto?
5. Are actual-vs-forecast surprise features usable from our real data, or do
   timestamp limitations force us to use scheduled-event risk only?
6. Does event context improve the portfolio supervisor more than the per-asset
   SAC observation?

## Final Recommendation

Adopt event context, but implement it as an input/data lane inside the weekly
walk-forward pool:

```text
Decision: ADD
Initial form: engineered event features
Initial target: ethusdt 4h and then FX assets
Primary criterion: repeated weekly train-tail + validation score
Secondary criterion: selected-candidate test and risk diagnostics
LLM role: extraction/classification only
Direct LLM trading: no
Stage C: denied
Broad GPU launch: no until a paired weekly-pool improvement exists
```

This keeps the useful part of the research idea while removing the parts that
would slow us down without directly improving profit/risk.
