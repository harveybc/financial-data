# Project 3 Weekly-Retrained Portfolio Protocol

Date: 2026-06-04
Status: ACTIVE CANONICAL PLAN

## Deadline Override - 2026-06-30

The week ending Monday 2026-07-06 is now in deadline mode because the RTX 5090
setup is expected to arrive Monday morning. On Monday 2026-07-06 the current
weekly-pool work plan will be paused and execution will switch to `doin`
decentralized optimization with the best model/data/configuration available at
that moment.

This override takes precedence over open-ended phase completion, stable-metric
triggers, and broad sweep completion.

Operational plan:

```text
work_plan/PROJECT3_DEADLINE_EXPERIMENT_PLAN_2026_06_30.md
```

Until the Monday switch, compute must be allocated by time-boxed experiment
lanes: finish enough of the current ETH risk baseline, then reserve explicit
windows for asset/timeframe diversity, data/feature representation diversity,
training-policy/oracle pretraining probes, and final full-year promotion of
the strongest candidates. Do not allow the existing ETH-only backlog to consume
all remaining time.

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
| `equal_weight_top_k_capped` | explicit v2 alias for equal-weight top-K with stream/asset/cluster caps |
| `score_weight_top_k_capped` | explicit v2 alias for score-weight top-K with caps |
| `score_inverse_vol_top_k_capped` | score times inverse prior volatility with caps |
| `score_inverse_cvar_top_k_capped` | score times inverse prior downside risk with caps/fallbacks |
| `score_inverse_vol_turnover_penalty` | inverse-vol allocation with explicit rebalance turnover cost |
| `score_inverse_cvar_turnover_penalty` | inverse-CVaR allocation with explicit rebalance turnover cost |
| `score_inverse_vol_portfolio_vol_target` | inverse-vol allocation with optional cash residual when prior portfolio vol exceeds target |

Full Markowitz/Black-Litterman/ML allocation is deferred until the simple
baselines exist and we can measure whether better covariance/expected-return
estimation is actually worth the complexity.

### Opportunity/Bloom Portfolio Allocator

The SOLUSDT 4h partial results observed in the 2026-06-29 OLAP transversal
analysis exposed an important portfolio hypothesis: some assets may enter
temporary high-opportunity regimes where a specialist agent deserves materially
higher allocation for a limited number of weeks. The portfolio layer must not
only diversify static streams; it must eventually detect these "bloom" regimes
early and rebalance toward them when evidence is available before the weekend
cutoff.

This is now an official research lane, not a conversational side idea.

Purpose:

- detect asset/model streams whose current pre-week state resembles previous
  high-return/high-RAP opportunity regimes;
- increase allocation to those streams while respecting drawdown, worst-week,
  correlation, and max-weight caps;
- detect when the bloom is decaying and reduce allocation or no-trade the
  stream;
- keep all decisions walk-forward causal.

Candidate inputs for the opportunity model:

- current train-tail and validation return/RAP/drawdown;
- slope and acceleration of recent validation or completed prior weekly
  evidence;
- worst-week RAP and loss-week rate in the available historical window;
- current market/context/event embeddings known before the rebalance cutoff;
- volatility, ATR, spread/cost, and liquidity state;
- cross-asset regime/context features;
- correlation or co-drawdown with other active candidates;
- similarity to prior historical weeks where an asset stream produced a
  strong test-week or validation-week bloom.

Candidate model families:

- rule baseline: rank by conservative pre-week signal and cap by drawdown;
- logistic/regression classifier for "next week positive RAP above threshold";
- gradient-boosted or random-forest meta-model on weekly candidate features;
- sequence model over prior weekly candidate metrics;
- later: event/context token transformer as a shared market-state encoder.

Walk-forward evaluation protocol:

```text
For each weekly rebalance anchor:
  1. fit/update the opportunity model using only prior weeks;
  2. score each available asset/model stream for the coming week;
  3. choose active streams and weights under portfolio caps;
  4. run the already-recorded next-week test returns/RAP as the portfolio outcome;
  5. store per-stream scores, weights, realized return, realized RAP,
     drawdown, turnover, and no-trade decisions in the OLAP cube.
```

Required comparison baselines:

- equal-weight top-K active streams;
- score-weight top-K active streams;
- inverse-vol and inverse-CVaR weighted top-K;
- static best historical stream;
- no-trade/cash baseline;
- CDT hurdle comparison on annual return and annual RAP.

Primary metrics:

- annual portfolio return;
- annual portfolio RAP;
- mean weekly portfolio return;
- mean weekly portfolio RAP;
- weekly max drawdown/adverse excursion;
- worst-week portfolio RAP;
- turnover cost;
- percentage of weeks in cash/no-trade;
- hit rate for detecting true opportunity weeks.

Guardrails:

- partial single-asset blooms are promotion candidates, not final proof;
- the allocator must never use current test-week performance to assign the
  current week's weights;
- no single asset may dominate the portfolio without an explicit max-weight
  override experiment;
- bloom detection must be evaluated against both return and RAP, because a
  high-return bloom that destroys RAP is just leverage, not intelligence.

Priority after the current risk-geometry jobs:

1. complete the most promising partial SOLUSDT 4h candidates to enough weekly
   coverage to verify whether the bloom is real;
2. build a portfolio-readiness dataset from `weekly_result_test_week_olap`
   using only causal pre-week features and next-week outcomes;
3. compare simple opportunity-score allocators before implementing a learned
   meta-allocator;
4. only then test transformer/context embeddings as inputs to the allocator.

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
portfolio_activations
portfolio_cutoff_manifests
```

The periodic portfolio runner is:

```text
agent-multi/tools/project3_portfolio_supervisor_runner.py
```

It is CPU-only and safe to run while the GPU workers continue training. Its
default mode writes stable `auto_latest_*` run IDs, replacing prior rows for the
same run instead of creating unbounded timestamped artifacts. The dashboard
exposes these results through:

```text
http://127.0.0.1:8787
http://127.0.0.1:8787/api/portfolio
```

The 2026-06-17 research review is accepted as the portfolio-supervisor v2
direction with the following practical translation:

- hard no-trade gates happen before allocation, not as soft optimizer wishes;
- weights use only train-tail, validation, prior realized weekly returns, and
  metadata known before the rebalance cutoff;
- same-anchor test returns are never used for weight selection, no-trade
  flags, covariance, CVaR, or allocation parameters;
- turnover and rebalance cost are first-class metrics and are subtracted from
  net portfolio return when configured;
- max stream, max asset, and max cluster exposure caps are explicit;
- every rebalance writes a cutoff manifest with `same_anchor_test_used=false`,
  `future_anchor_used=false`, and `stage_c_access=DENIED`;
- equal-weight and score-weight remain mandatory baselines because optimized
  allocators can underperform when expected returns and risk estimates are
  short-history/noisy.

This tool is not the final production allocator. It is the baseline and v2
deterministic simulator that makes portfolio behavior measurable while the
per-asset model search continues. HRP, shrunk-covariance optimization,
Black-Litterman, Kelly sizing, and learned meta-allocators are deferred until
the v2 deterministic layer produces enough stable multi-asset weekly history.

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
project3-weekly-supervisor-persistent.service
project3-weekly-phase-orchestrator.service
project3-weekly-adaptive-scheduler.service
project3-portfolio-supervisor-runner.service
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

Active phase chain, as updated on 2026-06-26:

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
4. `event_token_transformer_phase_next_v1`
   - tiny train-only `event_token_transformer_v1` context encoder;
   - creates `ctx_evt_tr_*` columns from `event_*` source columns;
   - keeps normalization and auxiliary readout targets strictly inside train;
   - transforms validation/test rows only with frozen train-fit parameters;
   - exists to compare against raw event-engineered inputs and
     `event_token_attention_v1`, not as the final large transformer.
5. `asset_preset_broadening_phase5_v1`
   - broaden from the event-context ETH probe to multiple liquid assets,
     4h/1h, and existing safe presets;
   - compare warm-start and fine-tune recent-window policies;
   - unique seed 5.
6. `oracle_bc_followup_phase6_v1`
   - generate train-window-only ZigZag oracle/anti-oracle labels for current
     top jobs;
   - run oracle behavior-cloning pretraining epochs 1, 3, and 5 followed by
     normal SAC;
   - keep validation/test oracle labels out of training.
7. `risk_adjusted_reward_phase7_v3`
   - clone only current evidenced winners, not the full search universe;
   - train with `dd_penalized_reward`;
   - rank level-1 checkpoints by risk-adjusted profit:
     `RAP = total_return - lambda * max_drawdown_fraction`;
   - use the corrected L1 business early-stopping score:
     `mean(train_tail_RAP, validation_RAP) - beta * abs(train_tail_RAP - validation_RAP)`;
   - start with `beta=0.25`;
   - keep test strictly report-only;
   - sweep `risk_penalty_lambda` values `0.25, 0.5, 1.0`;
   - sweep `rel_volume` values `0.05, 0.075, 0.10`;
   - cap the follow-up to the top 4 candidates with enough completed weekly
     anchors and at most 16 cloned anchors per candidate.
8. `sltp_risk_geometry_phase8_v3`
   - clone only current evidenced winners, not the full search universe;
   - preserve the historical control:
     `rel_volume=0.05`, `SL=2*ATR`, `TP=3*ATR`;
   - compare fixed ATR SL/TP geometry against exposure-aware SL/TP geometry;
   - enforce the business constraint that tested profiles have
     `TP_distance >= SL_distance`;
   - treat `rel_volume=0.50` as the maximum normal business exposure-risk
     reference, so `business_risk_fraction = rel_volume / 0.50`;
   - include high-exposure conservative profiles and a `margin_aware_atr`
     profile with planned-loss cap;
   - train with `dd_penalized_reward`;
   - select checkpoints by the corrected L1 score:
     `mean(train_tail_RAP, validation_RAP) - 0.25 * abs(train_tail_RAP - validation_RAP)`;
   - keep test strictly report-only;
   - write SL/TP dimensions into `result_json` for OLAP/Metabase:
     `rel_volume`, `business_risk_fraction`, `sltp_risk_mode`, `atr_period`,
     `k_sl`, `k_tp`, `reward_risk_ratio`,
     `stop_loss_atr_exposure_multiplier`, and
     `take_profit_atr_exposure_multiplier`.
9. Adaptive top-winner seed extension
   - if all configured phases already exist and the pool drains, extend the
     current top completed jobs with additional seeds 6 through 9, capped per
     job, to avoid idle machines without inventing unrelated work.

The heavier transformer/token encoder is specified separately and now has a
small first implementation:

```text
work_plan/PROJECT3_EVENT_TOKEN_TRANSFORMER_AGENT_SPEC_2026_06_17.md
```

Acceptance remains comparative: demote it if it fails to beat both raw
event-engineered inputs and `event_token_attention_v1` after enough completed
weekly anchors, or if any leakage manifest violation appears.

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

Operational status protocol:

- Every status report must query the SQLite pool live; do not rely on memory,
  stale terminal text, or dashboard impressions.
- Report time and ETA in `America/Bogota`.
- Always include queue counts for `done`, `pending`, `running`, `failed`,
  `deferred`, and `superseded`.
- Always include active machines, current subjob, heartbeat age, GPU summary,
  and percent progress when available.
- Stale detection:
  - heartbeat age greater than 5 minutes is `STALE`;
  - heartbeat age greater than 15 minutes or missing machine row is `DOWN`;
  - a machine reporting `running` with no progress and no GPU activity must be
    inspected before assuming useful work is happening.
- End every status report with an explicit machine alert block:
  `ALERTA MAQUINAS: ninguna caida/stale` or a loud list of affected machines.
- Never report a model as yearly/annual unless
  `weekly_result_test_year_olap.has_near_full_year_coverage = 1`.

Risk-adjusted follow-up policy:

- profit-only jobs remain the baseline and are not retroactively re-ranked;
- every completed job should expose comparable RAP fields when available:
  `train_tail_risk_adjusted_total_return`,
  `validation_risk_adjusted_total_return`,
  `test_risk_adjusted_total_return`, and
  `train_validation_risk_adjusted_composite_score`;
- risk-adjusted jobs set `selection_metric = risk_adjusted_return`, so level-1
  early stopping still uses train-tail plus validation, but on RAP instead of
  raw return;
- corrected L1 score, active from 2026-06-26:

  ```text
  train_score = train_tail_RAP when selection_metric=risk_adjusted_return
  val_score   = validation_RAP when selection_metric=risk_adjusted_return
  L1          = 0.5 * (train_score + val_score)
                - beta * abs(train_score - val_score)
  beta        = 0.25 initial value
  ```

  This preserves the train-tail plus validation rule while penalizing models
  whose validation gain is not supported by the most recent train window.
- the level-2/DEAP/adaptive layer must rank candidates by stable risk-adjusted
  evidence, not by the single largest weekly peak. The active L2 proxy is:

  ```text
  L2 = mean(L1_week) - gamma * std(L1_week) - delta * max(0, -worst_L1_week)
  gamma = 0.25 initial value
  delta = 0.50 initial value
  ```

  The scheduler can still keep probe anchors for exploration, but after enough
  evidence it must defer candidates with weak mean or weak L2 score.
- implementation note, 2026-06-26:
  - `agent-multi/pipeline_plugins/rl_pipeline_with_validation.py` supports
    `selection_metric = risk_adjusted_return` and
    `l1_generalization_gap_penalty_beta`;
  - `agent-multi/tools/project3_weekly_worker.py` records both raw-return and
    RAP summaries, plus the corrected L1 score fields, so historical
    profit-only and new RAP jobs can be compared;
  - `risk_adjusted_reward_phase7_v1` and `sltp_risk_geometry_phase8_v1` are
    historical first passes and should not be mixed with corrected L1 scoring;
  - `risk_adjusted_reward_phase7_v2` and `sltp_risk_geometry_phase8_v2` are
    superseded partial-source plans if they were generated from candidates
    without near-full-year validation coverage;
  - `risk_adjusted_reward_phase7_v3` and `sltp_risk_geometry_phase8_v3`
    supersede v1/v2 for the next execution block because they test the missing
    trade-level risk surface with corrected L1/L2 metrics and source candidates
    selected from near-full-year validation evidence:
    `rel_volume`, SL/TP geometry, and exposure-aware SL/TP;
  - RAP v1 uses equity max drawdown from the split summaries. Per-order maximum
    adverse excursion remains the stronger future refinement, but phase 8 now
    records enough SL/TP/exposure dimensions to decide which trade-risk family
    deserves that deeper instrumentation.

## Trade-Level Risk And SL/TP Tuning - 2026-06-23

The current order plugin is:

```text
gym-fx/strategy_plugins/direct_atr_sltp.py
```

Historical baseline behavior:

```text
strategy_plugin = direct_atr_sltp
atr_period = 14
k_sl = 2.0
k_tp = 3.0
rel_volume = 0.05
size_mode = notional
leverage = 1.0
```

For a long order:

```text
SL = close - k_sl * ATR
TP = close + k_tp * ATR
```

For a short order:

```text
SL = close + k_sl * ATR
TP = close - k_tp * ATR
```

`rel_volume` is the primary business exposure knob, but the realized loss at
the stop also depends on the SL distance:

```text
planned_stop_loss_fraction ~= rel_volume * leverage * (k_sl * ATR / price)
```

Therefore, the plan separates:

- exposure risk: how much notional/equity is exposed by `rel_volume`;
- stop-loss risk: how far price may move before the SL closes the position;
- path risk: max drawdown / adverse excursion while the order is open.

Business convention:

```text
max_risk_rel_volume = 0.50
business_risk_fraction = rel_volume / 0.50
```

This preserves the historical baseline:

```text
rel_volume = 0.05 => business_risk_fraction = 0.10
```

`rel_volume > 0.50` is not part of the normal research sweep unless an
operator explicitly creates a separate unsafe/high-leverage stress test.

The new SL/TP modes are:

| Mode | Meaning |
| --- | --- |
| `fixed_atr` | Historical behavior: `SL=k_sl*ATR`, `TP=k_tp*ATR`. |
| `rel_volume_aware_atr` | Preserves the baseline at `rel_volume=0.05`, then shrinks effective ATR multiples as exposure approaches `rel_volume=0.50`, while enforcing `TP >= SL`. |
| `margin_aware_atr` | Same exposure-aware logic plus an optional cap on planned stop-loss fraction. |

The first executable trade-risk phase is:

```text
sltp_risk_geometry_phase8_v3
```

It is deliberately compact. It tests:

- the exact historical control;
- fixed ATR geometries at baseline exposure;
- higher `rel_volume` conservative profiles;
- `rel_volume_aware_atr` profiles;
- one `margin_aware_atr` high-exposure profile.

It does not launch a full Cartesian sweep of every `rel_volume`, `k_sl`,
`k_tp`, `atr_period`, and risk penalty value. The next expansion must be based
on Metabase/OLAP evidence from this phase.

OLAP support:

```text
Database: financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

The weekly pool database is the canonical OLAP cube for experiment evidence.
Do not quote ad-hoc console means, partial worker summaries, or single-week
values as business results. Every reported number must come from the cube or
from a reproducible query against the same schema.

Canonical OLAP views:

| View | Grain | Use |
| --- | --- | --- |
| `weekly_result_olap` | one completed subjob/seed result | Audit raw split metrics, paths, configs, SL/TP dimensions, and candidate provenance. |
| `weekly_result_test_week_olap` | one unique test week per candidate/profile dimension | Collapse duplicate seed/subjob rows before evaluating weekly performance. |
| `weekly_result_test_year_olap` | one test year per candidate/profile dimension | Business-facing annual coverage check and yearly aggregate source. |
| `weekly_result_validation_week_olap` | one unique validation week per candidate/profile dimension | Collapse duplicate rows before annual validation selection. |
| `weekly_result_validation_year_olap` | one validation year per candidate/profile dimension | Validation-year coverage check and annual validation aggregate source. |
| `weekly_result_full_year_protocol_olap` | one annual validation/test block per candidate/profile dimension | Only source for the explicit full-year validation/test protocol. |
| `weekly_result_artifact_olap` | one indexed file artifact per subjob | Audit every persisted `results.json`, log, progress file, policy, config, context manifest, and return trace. |

Physical artifact table:

```text
result_artifacts
```

Required columns:

```text
subjob_id
artifact_type
path
size_bytes
mtime
sha256
content_tail
metadata_json
created_at
updated_at
```

The artifact table is intentionally physical, not a transient dashboard query.
It is the audit index that prevents completed work from being lost when logs,
remote workers, or local run directories become hard to inspect manually.
Large binary/text files stay on disk, but the cube stores their path, size,
mtime, SHA-256 hash, JSON metadata when safe, and a bounded log tail for log
artifacts.

Artifact types currently indexed:

```text
results_json
summary_json
stdout_log
training_progress_json
policy_zip
config_out_json
return_trace
context_embedding_json
json
log
artifact
```

`weekly_result_olap` exposes:

| Field group | Columns |
| --- | --- |
| Identity | `subjob_id`, `job_id`, `candidate_id`, `asset`, `timeframe`, `model_family`, `train_years`, `training_policy`, `experiment_phase`, `evaluation_protocol`, `evaluation_block`, `configured_validation_year`, `configured_test_year`, `annual_eval_min_weeks`, `olap_profile_key` |
| Data provenance | `input_data_file`, `feature_count`, `config_path`, `run_dir` |
| Walk-forward windows | `weekly_anchor_id`, `train_start`, `train_end`, `validation_start`, `validation_end`, `test_start`, `test_end`, `validation_year`, `validation_week_start`, `test_year`, `test_week_start` |
| Selection scores | `score`, `raw_score`, `selection_metric`, `composite`, `risk_composite`, `risk_penalty_lambda`, `l1_score`, `l1_mean_score`, `l1_gap`, `l1_gap_penalty`, `l1_gap_beta` |
| Return metrics | `train_tail_return`, `validation_return`, `test_return` |
| Drawdown metrics | `train_tail_drawdown`, `validation_drawdown`, `test_drawdown` |
| Risk-adjusted profit | `train_tail_rap`, `validation_rap`, `test_rap` |
| Trade-risk dimensions | `rel_volume`, `business_risk_fraction`, `strategy_plugin`, `sltp_risk_mode`, `atr_period`, `k_sl`, `k_tp`, `reward_risk_ratio`, `stop_loss_atr_exposure_multiplier`, `take_profit_atr_exposure_multiplier` |
| Execution counts | `train_tail_trades`, `validation_trades`, `test_trades` |

`weekly_result_test_week_olap` is the first source to use for plots over time.
It groups completed subjobs by the full candidate/profile key plus
`test_week_start`, then averages seed/subjob duplicates into:

```text
mean_train_tail_return
mean_validation_return
mean_test_return
mean_l1_score
mean_l1_mean_score
mean_l1_gap
mean_l1_gap_penalty
mean_train_tail_drawdown
mean_validation_drawdown
mean_test_drawdown
mean_train_tail_rap
mean_validation_rap
mean_test_rap
min_test_rap
max_test_rap
subjob_rows
candidate_rows
```

`weekly_result_test_year_olap` is the only view that may be used for
year-level business language. It groups the weekly view by candidate/profile
and `test_year`, then exposes:

```text
unique_test_weeks
subjob_rows
candidate_rows
first_test_week
last_test_week
mean_weekly_test_return
sum_weekly_test_return
observed_test_return
projected_annual_test_return_52w
mean_weekly_test_rap
mean_weekly_test_drawdown
sum_weekly_test_drawdown
sum_weekly_test_rap
observed_test_rap
projected_annual_test_rap_52w
annual_test_rap
worst_weekly_test_rap
best_weekly_test_rap
mean_weekly_l1_score
mean_weekly_l1_gap
coverage_ratio_52w
has_near_full_year_coverage
```

Interpretation rules:

- `mean_weekly_*` values are averages over unique weekly test windows, not a
  literal one-year account equity curve.
- A row is **not** allowed to be called a yearly evaluation unless
  `has_near_full_year_coverage = 1`.
- `has_near_full_year_coverage = 1` requires at least 48 unique test weeks.
- `coverage_ratio_52w = unique_test_weeks / 52.0` must be displayed beside any
  year-level metric.
- Test metrics remain report-only. They must never enter checkpoint selection,
  level-2/DEAP fitness, portfolio allocation, no-trade gates, or scheduler
  promotion decisions.
- For CDT comparison, use `weekly_result_test_year_olap` rows with near-full
  coverage, then derive annualized return in Metabase or a report as
  `(1 + mean_weekly_test_return)^52 - 1`. If coverage is below 48 weeks, the
  row is only a partial probe.
- For partial probes, `annual_test_return` and `annual_test_rap` must not be
  described as annualized. They are legacy aliases for the observed covered-week
  sums. Use `projected_annual_test_return_52w = 52 * mean_weekly_test_return`
  and `projected_annual_test_rap_52w = 52 * mean_weekly_test_rap` when a
  partial result is intentionally projected to a 52-week scale. The projection
  must always be displayed with `unique_test_weeks` and `coverage_ratio_52w`.
- Status, dashboard, and Metabase reports must distinguish three quantities:
  `mean_weekly_*` (average weekly result), `observed_test_*` (sum over covered
  weeks), and `projected_annual_test_*_52w` (52-week projection from the weekly
  mean). Only near-full-year rows may be discussed as actual yearly evidence.
- `sum_weekly_test_rap` and `annual_test_rap` are the same additive full-year
  RAP diagnostic for covered test-year rows. They are not compounded annual
  capital growth.
- `sum_weekly_test_return` and `annual_test_return` are the same additive
  full-year return diagnostic for covered test-year rows. Dashboards and status
  reports must show `annual_return` explicitly instead of forcing the user to
  infer it from `sum_weekly_return`.
- Status and dashboard responses must always show, when available:
  `mean_weekly_return`, `annual_return`, `mean_weekly_rap`, `annual_rap`,
  `mean_weekly_drawdown`, `unique_weeks`, and coverage.
- Any status answer must distinguish partial weekly coverage from full-year
  coverage and must name `unique_test_weeks`, `first_test_week`,
  `last_test_week`, and `coverage_ratio_52w`.
- Annual OLAP grouping must include `candidate_id`. Do not group only by
  `training_policy`, because that merges distinct fine-tune windows such as
  12m, 6m, and 3m into one fake candidate.

Full-year validation/test protocol, active from 2026-06-25:

```text
evaluation_protocol = full_year_validation_test_v1
configured_validation_year = 2022
configured_test_year = 2023
annual_eval_min_weeks = 48
```

This protocol exists because partial batches can discover candidates, but they
must not answer the business question. A valid comparison requires two explicit
annual blocks per candidate:

- `evaluation_block = validation_year`: at least 48 weekly retrained validation
  windows inside the configured validation year. This block is for model/family
  selection.
- `evaluation_block = test_year`: at least 48 weekly retrained test windows
  inside the configured test year. This block is report-only and is the source
  for the business-facing test-year RAP.

The current executable annual plan is:

```text
financial-data/experiments/weekly_walkforward_pool/auto_phase_plans/full_year_ethusdt_4h_2022val_2023test_v1.json
```

It was generated with:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python \
  financial-data/_scripts/workers/project3_weekly_pool_plan_worker.py \
  --input-data-file financial-data/experiments/stage_a_screening/inputs/ethusdt/4h/kitchen_sink_guarded/train.csv \
  --asset ethusdt \
  --timeframe 4h \
  --feature-preset kitchen_sink_guarded \
  --execution-profile annual_4y_2022val_2023test_rap \
  --feature-column-mode all_available \
  --train-years 4 \
  --policies scratch,fine_tune_recent_window \
  --fine-tune-months 12,6,3 \
  --annual-validation-year 2022 \
  --annual-test-year 2023 \
  --annual-min-weeks 48 \
  --early-stop-train-tail-days 7 \
  --validation-days 7 \
  --test-days 7 \
  --min-train-rows 500 \
  --output-dir financial-data/experiments/weekly_walkforward_pool/auto_phase_plans \
  --plan-stem full_year_ethusdt_4h_2022val_2023test_v1
```

Generation result:

```text
jobs: 8
subjobs: 416
skipped windows: 0
validation-year rows per variant: 52
test-year rows per variant: 52
```

Canonical query for the best valid test-year RAP:

```sql
SELECT
  asset,
  timeframe,
  configured_validation_year,
  configured_test_year,
  metric_year AS test_year,
  unique_weeks,
  first_week,
  last_week,
  olap_profile_key,
  training_policy,
  mean_weekly_return,
  mean_weekly_drawdown,
  mean_weekly_rap,
  sum_weekly_rap,
  coverage_ratio_52w
FROM weekly_result_full_year_protocol_olap
WHERE metric_block = 'test_year'
  AND has_near_full_year_coverage = 1
ORDER BY mean_weekly_rap DESC
LIMIT 1;
```

If this query returns no rows, the honest answer is: no completed full-year
test RAP exists yet. Do not replace it with the best 10-week or partial
exploratory row.

Artifact backfill:

```text
agent-multi/tools/project3_weekly_artifact_backfill.py
```

Canonical command:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python \
  agent-multi/tools/project3_weekly_artifact_backfill.py \
  --db financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite \
  --runs-root agent-multi/experiments/weekly_walkforward_pool/runs \
  --apply
```

Rules:

- The backfill is idempotent and uses `UPSERT`.
- It must not delete, move, or truncate run directories.
- It may enrich `subjobs.result_json` only by filling missing summary keys from
  `results.json`/`summary.json`; it must preserve existing metric values unless
  run with an explicit refresh flag.
- It records one `pool_events` row with the backfill report.
- It indexes orphan run directories under their directory name if they exist,
  but the expected steady-state orphan count is zero.

Backfill applied on 2026-06-25:

```text
subjobs_seen: 13440
run_dirs_seen: 7998
artifact_files_seen: 55652
artifact_rows_upserted: 55652
orphan_run_dirs: 0
result_summaries_updated: 7995
```

Artifact inventory after backfill:

```text
return_trace: 27828 files
policy_zip: 7998 files
stdout_log: 7998 files
results_json: 7995 files
training_progress_json: 1857 files
config_out_json: 1854 files
context_embedding_json: 61 files
other artifact/json/log: 61 files
```

Current correction note, 2026-06-25:

- The active SOLUSDT 4h risk-geometry queue currently produces only 10 unique
  2023 test weeks for several profiles because the active source file does not
  contain enough usable history for the intended 3-year train plus full-year
  test evaluation.
- Example partial row:
  `asset=solusdt`, `timeframe=4h`, `olap_profile_key=aware_rv0p50_base`,
  `test_year=2023`, `unique_test_weeks=10`,
  `coverage_ratio_52w=0.1923`, `has_near_full_year_coverage=0`.
- That row may be used as a short probe for scheduling, but it must not be
  described as annual RAP or annual return.
- The next full-year comparison must either regenerate the financial-data
  source files with enough history or enqueue assets/timeframes whose input
  files support the chosen `train_years + validation + test-year` windows.

Metabase/manual plots should be built from these views, not from raw log files:

- profit vs `rel_volume`;
- RAP vs `rel_volume`;
- drawdown vs `rel_volume`;
- RAP vs `k_sl` / `k_tp`;
- test return vs test drawdown by `sltp_risk_mode`;
- asset/timeframe sensitivity to `business_risk_fraction`.

Portfolio-level risk remains in scope, but sequence matters:

1. first tune trade-level exposure and SL/TP geometry;
2. then run/compare portfolio allocation on top of the better per-asset streams;
3. later add portfolio-level risk objectives if they add value beyond
   trade-level RAP and no-trade/activation gates.

CDT comparison baseline:

- Colombian CDT return is a low-risk yearly benchmark, not a trading strategy.
  A 12.0% EA CDT corresponds to roughly 0.218% compounded weekly; 12.6% EA is
  roughly 0.228% compounded weekly.
- For covered held-to-maturity CDT exposure, volatility/drawdown are treated
  as approximately zero for dashboard comparison. The residual risks are
  inflation, liquidity, reinvestment, entity failure above deposit insurance,
  and country/currency risk.
- Candidate reports must compare against CDT using annualized geometric test
  return, annualized weekly volatility, downside volatility, max drawdown,
  CVaR, loss-week rate, Sortino/Calmar-like ratios, and excess return over the
  weekly CDT hurdle. Raw return alone is no longer enough once a candidate is
  near the CDT hurdle.
- dashboard note, 2026-06-23:
  - the AdminLTE dashboard exposes a `Risk vs Profit Map`;
  - X axis is average weekly test max drawdown fraction;
  - Y axis is average weekly test net `total_return`;
  - dotted horizontal lines show 12.0% and 12.6% Colombian CDT effective annual
    references converted to weekly geometric returns;
  - old completed jobs are visually backfilled from their `results.json`
    `splits` when DB summaries do not yet contain RAP/drawdown fields.

## Required External Agent Specs

The current code implementation is large enough to split across agents. Use:

```text
work_plan/PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md
```

That file contains copy-ready specs for coding agents.

## Adaptive Scheduler Update - 2026-06-22

The pool must not finish large factorial sweeps blindly. A broad batch is useful
only until it gives enough evidence to decide what deserves more GPU time.

Active scheduler:

```text
agent-multi/tools/project3_weekly_adaptive_scheduler.py
```

Current policy:

- applies to the active broadening and risk follow-up lanes, including
  `asset_preset_broadening_phase5_v1`, `risk_adjusted_reward_phase7_v3`, and
  `sltp_risk_geometry_phase8_v3`;
- does not delete completed results;
- does not touch running jobs;
- marks low-value pending jobs as `deferred`, with the reason stored in
  `subjobs.error` and a summary event in `pool_events`;
- keeps at most 8 probe anchors for candidates without enough evidence;
- after at least 5 completed weekly probes, defers candidates whose mean score
  is below 0 or whose robust L2 proxy is below 0.0005:

  ```text
  L2 = mean(L1_week) - 0.25 * std(L1_week) - 0.50 * max(0, -worst_L1_week)
  ```

- keeps only the top 2 evidenced candidates per asset/timeframe before allowing
  more anchors for that group.

This is a pragmatic successive-halving layer, not a full DEAP/GA optimizer. The
DEAP/evolutionary layer remains a later upper-level search over meaningful
business genes: asset, timeframe, feature preset, training policy, train window,
fine-tune window, event-token profile, oracle-pretraining flag, and portfolio
allocator. It should not be used yet for low-level SAC hyperparameters until we
have a clearly profitable lane worth refining.

Applied once on 2026-06-22:

- pending reduced from 4877 to 2393;
- 2484 pending subjobs marked `deferred`;
- 3 running jobs preserved;
- scheduler daemon started with a 30-minute interval so future evidence can
  continue pruning redundant pending work.

## L1/L2 Risk Rollout - 2026-06-26

Implementation status:

- L1 checkpoint selection now uses:

  ```text
  L1 = mean(train_tail_score, validation_score)
       - 0.25 * abs(train_tail_score - validation_score)
  ```

- In risk phases, `train_tail_score` and `validation_score` are RAP values:

  ```text
  RAP = total_return - risk_penalty_lambda * max_drawdown_fraction
  ```

- L2/adaptive scheduling uses:

  ```text
  L2 = mean(L1_week) - 0.25 * std(L1_week) - 0.50 * max(0, -worst_L1_week)
  ```

- Status/dashboard reports must show mean weekly return, mean weekly RAP,
  annual RAP, mean weekly drawdown, unique week coverage, and machine freshness.

Operational rollout:

- `risk_adjusted_reward_phase7_v2` and `sltp_risk_geometry_phase8_v2` were
  superseded because their source selection could draw from partial 10-week
  candidates.
- `risk_adjusted_reward_phase7_v3` and `sltp_risk_geometry_phase8_v3` source
  from near-full-year validation/test physical jobs for the top annual
  candidates.
- The first active batch is deliberately compact:
  - run `sltp_risk_geometry_phase8_v3` first;
  - keep 2 weekly probes per profile/job;
  - defer the remaining phase8 anchors until first evidence;
  - defer phase7 v3 until phase8 gives useful evidence.

This keeps all GPUs busy without committing days to an unfiltered factorial
sweep.

## Doin Decentralized Optimization Integration - 2026-06-30

After the current weekly walk-forward lanes identify a stable best candidate
family, Project3 must be made compatible with the existing `doin`
decentralized DEAP/blockchain optimizer.

This is an official future execution lane. It exists because the next hardware
expansion includes an ASUS ROG Astral RTX 5090 32GB plus external GPU enclosure
and dedicated power supply. The new node should not merely run the current pool
worker; it should also be usable as a high-throughput `doin` optimizer node
when the candidate family is mature enough for evolutionary search.

### Trigger Condition

2026-06-30 operational override: for the week before the RTX 5090 arrives, do
not spend engineering time implementing `doin` internals here. The fixed switch
date is Monday 2026-07-06; until then, the active task is the deadline
experiment plan above. `doin` implementation details will be handled separately
component-by-component during the weekend.

Do not start broad `doin` optimization while the candidate family is still
unstable. Start this lane when we have:

- a best or near-best full-year candidate family with enough weekly coverage;
- fixed leakage-safe train/validation/test protocol;
- known dataset/preset and environment wrapper;
- stable metric set: weekly return, annual return, weekly RAP, annual RAP,
  drawdown, worst-week RAP, trades, coverage, and runtime;
- a short list of meaningful high-level hyperparameters to optimize.

### Agent-To-Optimize Wrapper

Create a callable Project3 optimization agent that `doin` can execute as a
candidate evaluator.

Required behavior:

- read one candidate JSON/config from `doin`;
- instantiate the Project3 trading environment used by the current weekly
  pool;
- apply the candidate hyperparameters and transformation plugin;
- run the configured weekly walk-forward evaluation anchors;
- return a deterministic metrics payload for `doin` and for Project3 OLAP;
- fail loudly on leakage, missing data, invalid parameter ranges, or incomplete
  coverage;
- never use current-week test results for training, checkpoint selection, early
  stopping, or portfolio weighting.

The wrapper output must include:

```text
candidate_id
asset
timeframe
dataset_profile
model_family
training_policy
train_years
fine_tune_window
feature_transform_plugin
hyperparameters
mean_weekly_return
annual_return
mean_weekly_rap
annual_rap
mean_weekly_drawdown
worst_weekly_rap
coverage_weeks
runtime_sec
machine_id
gpu_name
seed
artifact_paths
```

### Common Agent JSON

One common config is shared by all machines. It describes what `doin` is allowed
to optimize, independent of the node that evaluates it.

Required contents:

- repository paths for `agent-multi`, `financial-data`, and any dataset roots;
- selected candidate family and model entrypoint;
- train/validation/test protocol and weekly anchor rules;
- asset/timeframe universe allowed for the run;
- dataset/profile names and feature presets;
- hyperparameter ranges and discrete choices;
- allowed risk geometry ranges: `rel_volume`, `business_risk_fraction`,
  `k_sl`, `k_tp`, `atr_period`, risk penalty;
- optional transformation plugin spec;
- metric objective, for example:

  ```text
  primary = annual_rap
  secondary = annual_return
  penalties = drawdown, worst_weekly_rap, incomplete_coverage, runtime
  ```

- hard constraints:
  - minimum weekly coverage;
  - no same-week test leakage;
  - max business risk;
  - max runtime per candidate;
  - required output schema.

### Per-Node Doin JSON

Each machine has its own node config. It references the common agent config but
defines local resources and decentralized network behavior.

Required contents:

- `node_id`, machine name, and role;
- GPU device IDs and concurrency level;
- local work directory and artifact directory;
- Python/conda environment;
- blockchain/doin network identity;
- neighbor nodes and discovery settings;
- champion exchange settings;
- local candidate queue size;
- checkpoint/restart policy;
- heartbeat interval;
- metrics publishing interval;
- maximum parallel candidates;
- per-machine resource limits.

The RTX 5090 node must support experiments with multiple concurrent candidate
evaluations because single small SAC candidates may not saturate the GPU.

### RTX 5090 / eGPU Benchmark Plan

The new 5090 should be benchmarked before assuming it is cost-effective for all
Project3 workloads.

Benchmark matrix:

1. same small SAC candidate, one worker:
   - omega RTX 4070 laptop;
   - dragon RTX 4090 laptop;
   - gamma RTX 5070 Ti laptop;
   - RTX 5090 eGPU host.
2. same candidate, multiple workers on the RTX 5090:
   - 1, 2, 3, 4 concurrent evaluators;
   - measure candidates/hour, GPU utilization, VRAM, CPU load, temperature,
     and failures.
3. larger future workloads:
   - event/context transformer encoder;
   - oracle behavior-cloning pretraining;
   - portfolio opportunity/bloom allocator;
   - larger batch/vectorized environment versions.
4. eGPU host comparison:
   - ROG Ally host;
   - RTX 5070 Ti laptop host;
   - any other available laptop/desktop host;
   - measure whether CPU, PCIe/eGPU bandwidth, memory, thermals, or storage
     bottleneck the card.

Decision metric:

```text
candidates_per_hour_per_dollar
candidates_per_hour_per_watt
usable_parallel_candidates
stability_over_12h
```

Expected hypothesis:

- for small current SAC jobs, the 5090 may not scale linearly because the
  environment/simulation can be CPU-bound;
- for multiple concurrent candidates or larger transformer/pretraining jobs,
  the 5090 should become much more valuable;
- buying future high-end GPUs should be justified by measured throughput, not
  theoretical CUDA core counts alone.

### OLAP / Blockchain Interop

`doin` already records a decentralized blockchain OLAP-like history of
candidate metrics. Project3 must preserve interoperability:

- each `doin` candidate should emit Project3-compatible metrics;
- `doin` blockchain metrics should be exportable into SQLite/Metabase;
- Project3 SQLite OLAP rows should include a `doin_run_id` or equivalent when
  results come from the decentralized optimizer;
- champion candidates discovered by `doin` must be replayable inside the
  standard Project3 weekly pool for final full-year validation.

### Implementation Order

1. Freeze the current best candidate family after the active work plan finishes
   or reaches an obvious plateau.
2. Write the Project3 candidate-evaluator wrapper for `doin`.
3. Write the common agent JSON schema and one concrete config.
4. Write node JSON templates for omega, dragon, gamma, and the future RTX 5090
   node.
5. Run a tiny deterministic smoke test with one candidate on one machine.
6. Run multi-node `doin` smoke with champion exchange.
7. Benchmark candidates/hour across machines.
8. Start evolutionary optimization only on meaningful high-level parameters,
   not low-level noise.
