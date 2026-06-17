# Project 3 Weekly-Retrained Portfolio Protocol

Date: 2026-06-04
Status: ACTIVE CANONICAL PLAN

## Decision

Project 3 is a weekly-retrained portfolio trading system. It is not a static
one-year benchmark and it is not a short-window smoke-test project.

The production-shaped loop is:

1. train or update models over the weekend using only data known before the
   decision cutoff;
2. validate on the next historical week during research;
3. test/simulate the following week only;
4. repeat across many historical weekly anchors;
5. aggregate results across weeks, seeds, costs, assets, and training-window
   lengths;
6. later use a portfolio supervisor to allocate capital and no-trade flags
   across the per-asset models.

The previous the previous short-window run family is obsolete for
optimization. Its artifacts were deleted. Tiny windows may be used only for
mechanical unit tests, never as evidence that a model/data/preprocessing choice
is good.

## Non-Negotiable Evaluation Unit

Every serious experiment is a collection of weekly subjobs.

```text
job:
  model/data/preprocessing/hyperparameter/training-policy candidate

subjob:
  one weekly anchor for that job

subjob split:
  train      = N years before validation window
  train_tail = configurable final slice of train used only for early-stop scoring
  validation = configurable calendar days immediately after training
  test       = configurable calendar days immediately after validation
```

The result of a job is the aggregate of its subjobs, not one lucky week.

Primary sweep:

```text
train_years in [1,2,3,4,5,6,7,8,9,10]
early_stop_train_tail_days in [7,14,28]
validation_days in [7,14,28]
test_days in [7,14,28]
```

The 4-year window is a strong prior from previous predictor work, but it is not
hard-coded as truth. The sweep must measure whether 1, 2, 3, 4, or more years
produce better repeated next-week profit/risk.

Early stopping is based on the average of the trading performance in the final
slice of the training window and the validation window:

```text
early_stop_score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

The full training dataset remains `train_years=N`; `train_tail` is only the
evaluation slice used for the early-stop score. Patience increments only when
this score does not improve by `l1_min_delta`; patience resets to zero whenever
the score improves and the checkpoint is saved.

## Training Policies To Compare

The first implementation must support three training policies as separate
families. Do not mix their scores in one label.

| Policy | Meaning | Research use |
| --- | --- | --- |
| `scratch_n_years` | Train from scratch for every weekly anchor using `train_years=N`. | Cleanest comparison for data, preprocessing, and hyperparameters. |
| `warm_start_4y_then_1y` | Initial model trained on 4 years, then weekly fine-tune using last 1 year plus optional replay. | Production-like candidate after scratch baselines exist. |
| `warm_start_4y_light` | Initial model trained on 4 years, then weekly light update using the same 4-year window. | Stability check against catastrophic forgetting. |

Initial orchestration should start with `scratch_n_years` because it gives the
least ambiguous comparison. Warm-start policies are then compared against the
best scratch candidates.

## Seasonality Policy

With 4 years of training, there are only about 4 direct examples of the exact
same week-of-year. That is too little to let week identity dominate the model.

Allowed seasonal features:

- hour sine/cosine;
- day-of-week sine/cosine;
- month sine/cosine;
- week-of-year sine/cosine;
- hours-to-Friday-close;
- Monday entry window flag;
- event-calendar risk score known before the cutoff.

Forbidden as primary decision keys:

- hard one-hot week-of-year as a dominant feature;
- any feature fitted using validation, test, or Stage C rows;
- any calendar/event value learned after the decision cutoff.

Seasonality is a soft context feature. Market state, volatility, liquidity,
trend, cost, and event risk must compete with it.

## Active Data/Input Search

For each target asset, the system may use:

- own-asset OHLCV and engineered features;
- other tradable assets as cross-asset inputs;
- macro/event/calendar features when available at the decision cutoff;
- paid-source features only when historical coverage, leakage safety, and
  marginal value are proven;
- market-state summaries and embeddings fitted train-only.

`target_asset` and `input_asset_mask` are separate genes. A model trading one
asset may use other asset prices/features as inputs.

## Weekly Portfolio Supervisor Layer

The product is a portfolio service, not a one-asset signal service.

Current scope boundary:

- **In scope now:** normalized control signals, per-asset model selection,
  no-trade flags, and weekly portfolio weights.
- **Out of scope now:** user-account plumbing, deposits, PAMM/social-trading
  execution, per-user capital accounting, and conversion of signals into
  broker-specific orders for each customer.

The system may later be consumed by a separate execution service that maps our
signals and normalized portfolio weights into user-specific trades. For current
research, portfolio weights are unit-capital normalized research outputs, not
customer-dollar instructions.

Each client account may hold several active asset streams at the same time.
The per-asset SAC agents decide trade direction/management inside their own
asset environment, but a higher layer decides every weekend:

- which asset/model streams are active for the coming week;
- which streams receive a no-trade flag;
- how much capital/order-size budget each active stream receives;
- portfolio-level caps such as max weight per asset, max number of active
  assets, and max exposure to highly correlated streams.

The weekly rebalance must use only information available before the simulated
next week:

- current subjob train-tail and validation performance;
- prior realized weekly strategy returns;
- prior covariance/downside-risk estimates;
- event/context/market-state embeddings known before the decision cutoff;
- broker cost/spread constraints and weekend-flat rules.

It must not use the next week test return when choosing weights.

Canonical architecture:

1. **Market/context representation layer**
   - converts multi-asset prices, event calendar data, event surprises,
     seasonal features, unsupervised market-state features, technical/fundamental
     inputs, and cross-asset context into fixed or variable-length market
     representations;
   - may be a simple engineered feature layer, train-only embeddings, or later
     a trading-language/market-description transformer.
2. **Per-asset specialist layer**
   - trains one or more agents specifically for each tradable target asset;
   - may consume its own asset data plus cross-asset/context embeddings;
   - outputs asset-specific trading policy evidence and weekly signal streams.
3. **Weekly portfolio supervisor**
   - chooses active asset/model streams and normalized weights for the coming
     week;
   - may start as rule/MPT/PMPT baselines and later become an ML/meta-allocator
     that consumes the same market/context representation.
4. **External execution/user layer**
   - deliberately deferred;
   - maps signals/weights to actual user orders, account-specific capital,
     broker constraints, and service-specific execution policies.

All trainable layers above must follow the same weekly walk-forward rule:

```text
fit/update using information available before the rebalance cutoff;
score selection with train-tail + validation;
record test only after selection;
repeat across all historical weekly anchors;
average weekly results for model and portfolio comparison.
```

Initial portfolio methods to compare:

| Method | Purpose |
| --- | --- |
| `equal_weight` | mechanical baseline for selected active streams |
| `score_weight` | allocate by current known composite signal |
| `score_inverse_vol` | MPT-style diagonal risk approximation using prior realized weekly volatility |
| `score_inverse_cvar` | post-modern/downside-risk approximation using prior realized weekly left-tail returns |

Full Markowitz/Black-Litterman/ML allocation is deferred until the simple
baselines exist and we can measure whether better covariance/expected-return
estimation is actually worth the complexity.

The first executable supervisor is:

```text
agent-multi/tools/project3_portfolio_supervisor.py
```

It reads completed weekly-pool subjobs, selects the best stream per asset for
each rebalance week using known composite scores, allocates weights with the
methods above, records weekly portfolio returns, and can write reproducible
SQLite tables:

```text
portfolio_runs
portfolio_weekly_returns
portfolio_allocations
```

This tool is not the final production allocator. It is the baseline simulator
that makes portfolio behavior measurable while the per-asset model search
continues.

## Event-Context Input Lane

The 2026-06-09 event-context addendum is now part of this protocol.

Canonical documents:

```text
work_plan/project3_orchestrator_event_context_representation_addendum_2026_06_09.md
work_plan/PROJECT3_RESEARCH_AGENT_PRAGMATIC_CONTEXT_2026_06_09.md
```

Event context is not a separate academic gate. It is a candidate input family
inside the weekly pool.

The first implementation target is:

```text
event_engineered_summary_v1
```

The correct order is:

1. audit event/calendar/news source coverage and timestamp semantics;
2. build point-in-time engineered features only from fields known before the
   model decision timestamp;
3. join those features into matched candidate input files;
4. enqueue matched baseline vs event-context jobs using the same weekly anchors;
5. rank by the existing early-stop/selection score:

```text
score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

Direct LLM trading, broad transformer work, and learned event-token encoders
are deferred until engineered event context proves practical value against a
matched baseline. If actual/forecast/revision/surprise fields do not have a
reliable `first_available_ts`, those fields are not allowed in trading
observations and may only appear in coverage/audit reports.

## Oracle Behavior Pretraining Lane

The ZigZag oracle and anti-oracle baselines are now also a future training
signal candidate, not only a chart reference.

This lane is explicitly pragmatic: it tries to transfer useful behavior from a
hindsight teacher into the trading policy, then verifies whether that improves
the existing weekly walk-forward score.

Allowed training signal:

- compute oracle labels only inside each training window;
- use the same execution sizing, pessimistic spread/cost assumptions, and
  weekend-flat rule as the SAC environment;
- encode labels as `oracle_action` in `{-1, 0, +1}`, `anti_oracle_action`,
  and a confidence weight from net move after cost;
- never train on validation/test oracle labels. Validation/test oracle values
  are reporting baselines only.

Candidate experiments:

- `oracle_bc_pretrain_then_sac`: behavior-cloning pretraining from train-window
  oracle actions, followed by normal SAC;
- `oracle_aux_loss_sac`: SAC with an auxiliary train-window oracle-action loss;
- `oracle_contrastive_anti_loss_sac`: encourage distance from anti-oracle
  behavior while preserving SAC reward optimization.

These experiments must use the same weekly anchors, assets, data inputs, and
selection rule as the current pool. Selection remains:

```text
score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

The goal is not to copy the oracle perfectly. The goal is to reduce the gap
between the current best composite and the averaged ZigZag oracle composite
without worsening out-of-sample test diagnostics.

Active execution note, 2026-06-15:

- the previous non-oracle pending/running pool items were stopped and marked
  `superseded`;
- oracle/anti-oracle train-only labels were generated for the current top 3
  composite candidates under
  `financial-data/experiments/oracle_behavior_pretraining/labels`;
- the first production batch is
  `oracle_bc_pretrain_then_sac_v1_top3_plan.json`, 52 subjobs across 3
  independent chains, intended to keep omega, dragon, and gamma pulling work
  in parallel;
- the first subjob in each chain starts without an external warm-start parent
  so the pool plan remains self-contained; subsequent weeks warm-start from
  the previous oracle-BC subjob in the same chain;
- scoring remains the same composite:

```text
score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

## Job Pool Architecture

The next code milestone is a persistent SQLite-backed job pool.

Default database:

```text
financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

Core tables:

```text
jobs:
  job_id
  status
  created_at
  updated_at
  target_asset
  timeframe
  model_family
  agent_plugin
  env_plugin
  pipeline_plugin
  training_policy
  train_years
  validation_days
  test_days
  feature_preset
  feature_selection_method
  preprocessing_profile
  selected_features_json
  input_data_file
  input_data_hash
  market_state_profile_id
  broker_profile
  cost_scenario
  hyperparameters_json
  stage_c_access
  notes

subjobs:
  subjob_id
  job_id
  status
  priority
  assigned_machine
  worker_pid
  claimed_at
  started_at
  finished_at
  heartbeat_at
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
  config_file
  run_dir
  stdout_log
  stderr_log
  evidence_file
  result_file
  failure_reason

results:
  result_id
  subjob_id
  job_id
  seed
  train_return
  validation_return
  test_return
  train_sharpe
  validation_sharpe
  test_sharpe
  test_max_drawdown
  test_cvar
  validation_trades
  test_trades
  validation_trades_per_week
  test_trades_per_week
  test_cost_to_gross_edge
  friday_force_close_violations
  broker_policy_violations
  action_entropy
  long_action_count
  short_action_count
  hold_action_count

machine_heartbeats:
  machine_id
  hostname
  gpu_name
  gpu_utilization
  gpu_memory_used
  gpu_memory_total
  active_subjob_id
  status
  updated_at
```

The DB is the source of truth. File artifacts are referenced from the DB, not
used as the only status source.

## Worker Pool Behavior

Each machine runs a worker loop:

1. send heartbeat with GPU/process status;
2. atomically claim the highest-priority pending subjob;
3. materialize the agent-multi config for that subjob;
4. run training/evaluation;
5. write evidence and result files;
6. insert metrics into SQLite;
7. mark subjob done/failed;
8. claim the next pending subjob.

The worker must never require the user to ask for status. It must keep working
until the queue is empty or a real mechanical blocker appears.

Machines:

- local/Omega: RTX 4070 Laptop, slow worker plus dashboard host;
- `dragon`: RTX 4090 Laptop, fastest GPU worker;
- `gamma`: RTX 5070 Ti Laptop, GPU worker.

Workers run at different speeds. The pool must not allocate fixed equal batches
that leave fast machines idle.

## AdminLTE Monitoring Dashboard

The next code milestone includes a local dashboard.

Default URL:

```text
http://127.0.0.1:8787
```

Required dashboard sections:

- global queue totals: pending, running, done, failed;
- machine cards: GPU, active subjob, ETA, heartbeat age;
- active subjobs: job id, weekly anchor, asset, timeframe, train window,
  validation window, test window, rows per split, seed, config, ETA;
- current best job: by aggregated composite score, with train-tail,
  validation, test, Sharpe, drawdown, CVaR, cost-to-gross-edge, and
  positive-week-rate diagnostics;
- training-window sweep: performance by `train_years=1..10`;
- data/preprocessing leaderboard;
- full reproducibility pane: selected features, preprocessing params,
  hyperparameters, data hash, config path, run path;
- failure table with exact failure reason;
- Stage C firewall status.

AdminLTE may be loaded from CDN for local monitoring, with a simple fallback
HTML table if network is unavailable. The server should use Python standard
library plus SQLite unless a dependency is explicitly justified.

## Aggregation Metrics

A job is ranked from aggregated weekly subjobs.

Primary metrics:

- mean, median, and IQM composite score, where weekly composite is
  `0.5 * train_tail_total_return + 0.5 * validation_total_return`;
- train-tail, validation, and test return diagnostics;
- percent of positive validation and test weeks;
- validation/test Sharpe and downside Sharpe;
- max drawdown and CVaR;
- cost-to-gross-edge ratio;
- trade frequency inside broker policy bands;
- action diversity / no degenerate always-one-action policy;
- seed stability;
- improvement versus baselines.

Test return is never the ranking metric. It is inspected only after a candidate
is selected by composite.

The first baseline set:

- no-trade/cash;
- buy-and-hold where meaningful;
- simple momentum;
- simple reversal;
- previous-week trend sign;
- equal-weight portfolio baseline later.

## Stage C Firewall

Stage C remains locked.

No subjob may use rows on or after:

```text
2025-01-01
```

until a final one-shot heldout evaluation is explicitly authorized. The pool
must store `stage_c_access="DENIED"` on every job and subjob during current
work.

## What Was Deleted

The obsolete short-window short-window artifacts, SAC smoke result
folders, auto-chain logs, pids, nohups, and remote launch logs were deleted
because they used windows such as:

```text
train_days = 28
val_days = 14
test_days = 14
```

Those results are not used for profit/risk conclusions and are not active
optimization evidence.

## Immediate Implementation Order

1. Implement SQLite schema and queue CLI.
2. Implement job/subjob materialization for weekly walk-forward splits.
3. Implement atomic worker claim/heartbeat/result recording.
4. Implement AdminLTE dashboard.
5. Create a tiny mechanical test queue with 2 assets, 1 timeframe, 2 anchors,
   and low timesteps to prove plumbing.
6. Create the first real scratch sweep:

```text
target_asset = btcusdt_perp first
timeframe = 4h first
train_years = 1..10
early_stop_train_tail_days = 7 initially, then 14/28 comparison
validation_days = 7 initially, then 14/28 comparison
test_days = 7 initially, then 14/28 comparison
anchors = representative pre-2025 weekly anchors
seeds = 0,1,2
```

7. After the pool and dashboard are stable, expand to more assets and 1h.

## Active Automated Runtime

As of 2026-06-07, the weekly walk-forward pool is operated as a persistent
queue system, not as manual one-off launches.

Active database:

```text
financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

Active dashboard:

```text
http://127.0.0.1:8787
```

Active local services:

```text
project3-weekly-dashboard.service
project3-weekly-worker.service
project3-weekly-supervisor.service
project3-weekly-phase-orchestrator.service
```

The supervisor is responsible for:

- keeping the dashboard alive;
- restarting or starting the persistent worker when needed;
- leaving an already-running worker alone;
- re-queuing stale `running` subjobs if the worker process is gone and the
  heartbeat is stale;
- keeping the machine polling the SQLite pool without waiting for manual
  status requests.

The phase orchestrator is responsible for:

- watching the same SQLite pool independently of manual status requests;
- doing nothing while `pending + running >= 120`;
- automatically generating and enqueuing the next useful phase when backlog
  falls below that threshold;
- using unique job/subjob ids for every generated phase so already-completed
  work is not repeated accidentally;
- recording its enqueue decisions in `pool_events`.

Active phase chain, as programmed on 2026-06-17:

1. `eventctx_seed_robustness_phase2_v1`
   - ETHUSDT 4h event-engineered context vs matched baseline;
   - scratch and warm-start policies;
   - 1-year and 3-year training windows;
   - seeds 1, 2, and 3.
2. `eventctx_metric_window_phase3_v1`
   - same ETHUSDT 4h event-context comparison;
   - train-tail early-stopping metric windows of 14 and 28 days;
   - validation/test still one week;
   - unique seed 4.
3. `event_token_embedding_phase4_v1`
   - first executable embedding lane;
   - per-subjob train-only `event_token_attention_v1` encoder;
   - creates `ctx_evt_*` columns from `event_*` source columns;
   - freezes train-fit encoder before transforming validation/test rows;
   - unique seed 6.
4. `asset_preset_broadening_phase5_v1`
   - broaden from the event-context ETH probe to multiple liquid assets,
     4h/1h, and existing safe presets;
   - compare warm-start and fine-tune recent-window policies;
   - unique seed 5.
5. `oracle_bc_followup_phase6_v1`
   - generate train-window-only ZigZag oracle/anti-oracle labels for current
     top jobs;
   - run oracle behavior-cloning pretraining epochs 1, 3, and 5 followed by
     normal SAC;
   - keep validation/test oracle labels out of training.
6. Adaptive top-winner seed extension
   - if all configured phases already exist and the pool drains, extend the
     current top completed jobs with additional seeds 6 through 9, capped per
     job, to avoid idle machines without inventing unrelated work.

The heavier transformer/token encoder is specified separately and should be
implemented only after the first train-only embedding lane is mechanically
validated:

```text
work_plan/PROJECT3_EVENT_TOKEN_TRANSFORMER_AGENT_SPEC_2026_06_17.md
```

The current active experiment queue compares:

- 4-year scratch baseline;
- scratch recent-window retraining;
- fine-tune recent-window chains that preserve prior policy weights;
- recent fine-tune windows of 12, 6, 3, and 1 months;
- weekly validation/test anchors before the Stage C firewall.

Selection/ranking policy:

- select by aggregated composite:
  `0.5 * train_tail_total_return + 0.5 * validation_total_return`;
- require trades in train-tail and validation;
- record test only after selection;
- never use test return in `score`.

## Required External Agent Specs

The current code implementation is large enough to split across agents. Use:

```text
work_plan/PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md
```

That file contains copy-ready specs for coding agents.
