# Project 3 Post-No-Promotion Review — ChatGPT 5.5 Pro Web Spec

**Spec executed:** `ChatGPT 5.5 Pro Web Spec` only.  
**Role:** external senior quant/RL research reviewer.  
**Repository access:** none; this memo uses the attached files and external primary/official references only.  
**Date:** 2026-05-14.  
**Stage C rule:** Stage C remains a one-shot held-out firewall using rows at or after `2025-01-01`. Nothing in this memo recommends unlocking, tuning on, inspecting, or repeating Stage C.  
**Algorithm rule:** PPO, SAC, and DQN remain fixed. No recommendation below changes the RL algorithms.  
**Business objective:** maximize the probability of finding real, cost-adjusted tradable signal with minimal wasted GPU and no false promotion theater.

---

## 1. Executive decision

The pragmatic decision is:

```text
NO_STAGE_C
NO_BROAD_GPU_RERUN
NO_CRYPTOQUANT_PAYMENT_YET
DIAGNOSE_FEATURE_ACTION_INSENSITIVITY_FIRST
```

The current post-session-calendar state is operationally clean but economically and statistically non-promotable:

- The full latest evidence universe has `1220` evidence files, `1220` traces found, and `0` evidence failures.
- Candidate statistical gates are `0/100`.
- DSR under `N_raw` is `0/633`.
- `promotion_allowed = false`.
- `stage_c_allowed = false`.
- The trial count for deflation is `5025`.
- The cluster/session-calendar diagnostic queue completed with `270/270` done and `0` failed.
- The diagnostic ranking exists, but no ranked candidate is promotable.
- The top `tech_stat` variants have distinct data hashes yet nearly identical action/trade/performance signatures.
- All top audited candidates are missing `feature_list_hash`, which is an evidence-contract gap.
- The CSV session-calendar feature diagnostic did not produce a Stage B-ready candidate.
- CryptoQuant historical/API access is not currently usable for Stage B because the available exported/API coverage is not sufficient for pre-2025 Stage B historical validation.

This is not a reason to stop Project 3. It is a reason to stop **wasting GPU on broad reruns that cannot answer the current question**.

The core question is no longer:

```text
"Which top candidate should go to Stage C?"
```

The correct question is:

```text
"Why are materially distinct feature inputs producing effectively identical policy behavior?"
```

Until that is answered, a larger GPU matrix is more likely to multiply false discoveries than produce profit.

---

## 2. Source-grounded findings from the attached files

### 2.1 Stage B readiness status

The latest readiness artifact reports:

```text
any_stage_b_ready: false
n_stage_b_ready: 0
total_candidates: 4933
stage_c_allowed: false
stage_c_decision: BLOCK_STAGE_C
stage_c_locked: true
statistical_summary:
  candidate_gate_pass: 0
  candidate_gate_fail: 100
  dsr_pass_n_raw: 0
  dsr_fail_n_raw: 633
  evidence_files: 1220
  evidence_pass: 1220
  trace_found: 1220
  trace_missing: 0
  trial_count_for_deflation: 5025
```

The most common status counts are:

```text
KILL_NON_POSITIVE_RETURN: 2761
KILL_NO_TRADES: 1154
KILL_NEGATIVE_SHARPE: 974
BLOCKED_DSR_DEFERRED: 19
BLOCKED_MISSING_EVIDENCE: 13
BLOCKED_FAMILY_ABLATION: 8
BLOCKED_BASELINE_COMPARISON: 4
```

Interpretation:

- The project is not blocked by lack of compute completion.
- It is blocked by a combination of economic failure, insufficient statistical support, missing/weak family evidence, and action/feature insensitivity.
- The validator is correctly preventing Stage C.

### 2.2 Top diagnostic candidates

The diagnostic ranking ranks `34` candidate rows and explicitly states:

```text
promotion_allowed rows: 0
Stage C allowed: false
```

The top ranked rows are effectively tied:

```text
1. ethusdt_4h_sac_tech_stat_full_candidate
2. ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate
3. ethusdt_4h_sac_tech_stat_full_plus_train_only_ood_score_candidate
4. ethusdt_4h_sac_tech_stat_full_plus_train_only_regime_probs_candidate
5. ethusdt_4h_sac_tech_stat_momentum_only_candidate
6. ethusdt_4h_sac_tech_stat_reduced_corr_v1_candidate
7. ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_session_calendar_candidate
8. ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_train_only_regime_probs_candidate
```

For the top entries, the ranking shows approximately:

```text
score: 23.7501
mean return: 0.002380
min return: -0.016487
mean SR: 0.000839
cost scenarios: 3
seed pass: 3
trade blockers: none in top rows
main blockers:
  DSR_RIGOROUS_FAIL
  FAMILY_REALITY_CHECK_FAIL
  PBO_DEFERRED_OR_FAIL
```

Interpretation:

- This is a research-triage list, not a promotion list.
- The top rows are not differentiated enough to justify a winner.
- DSR/PBO/family gates are not “academic decoration” here. They are telling us that the apparent advantage is tiny, heavily searched, and not robust enough to risk Stage C.

### 2.3 Feature/action audit

The feature/action audit reports:

```text
top_n: 12
audited_candidates: 12
feature_list_hash_missing_candidates: 12
distinct_data_hashes: 12
identical_performance_signature_groups: 1
largest_identical_performance_group: 11
stage_c_allowed: false
```

The top `tech_stat` variants have distinct data hashes, but the action/trade/performance signatures are almost identical:

```text
mean OOS trades: 368.13
mean exposure: 0.5122
mean action std: 0.095240
same-performance clue: yes
```

The `baseline_12_candidate` is close but not in the identical group:

```text
mean OOS trades: 384.27
mean exposure: 0.5142
mean action std: 0.098165
```

Interpretation:

- The feature variants are not all accidentally pointing to the same data file, because `distinct_data_hashes = 12`.
- But the policy response is almost invariant to major feature differences.
- Missing `feature_list_hash` prevents the evidence layer from proving exactly which feature list reached the policy.
- The next step belongs in observation/action/reward/evidence plumbing diagnostics, not a broad GPU expansion.

### 2.4 Data context and paid source gap

The data-context file says the environment enforces a Friday/session close rule, while inspected `tech_stat` inputs initially did not expose explicit time-to-Friday or bars-to-force-close features. It also says the environment observation contains:

```text
position
equity_norm
unrealized_pnl_norm
steps_remaining_norm
```

but does **not** expose:

```text
bars_to_force_close
hours_to_force_close
```

as environment state fields.

The feature materializer later produced CSV session/calendar variants with 19 deterministic timestamp features, including:

```text
calendar_is_force_close_zone
calendar_is_friday_close_day
calendar_is_friday_force_close_bar
calendar_hours_to_friday_close
calendar_bars_to_friday_close
calendar_hours_to_next_friday_close
calendar_bars_to_next_friday_close
```

The diagnostic packet ran:

```text
270 locked configs = 3 variants x 5 seeds x 3 costs x candidate+5 baselines
270/270 done
0 failed
```

and still produced:

```text
0/100 candidate statistical gates passed
0 DSR passes under N_raw
promotion_allowed = false
stage_c_allowed = false
```

Interpretation:

- CSV calendar features alone did not solve the problem.
- That does not prove time-to-force-close context is irrelevant.
- The still-untested distinction is whether force-close context must be part of the **live environment state** alongside position/equity/unrealized PnL/steps remaining, not merely another CSV feature.
- The right next coding task is an environment observation-state audit and, if justified, a small counted diagnostic adding `bars_to_force_close` / `hours_to_force_close` to the live observation dictionary.

### 2.5 CryptoQuant status

The paid-source spec says CryptoQuant is not immediately runnable for Stage B because the acquired/API payload covers only a recent 2026 window. It also says not to launch CryptoQuant historical ablations unless historical export/API coverage is confirmed.

Interpretation:

- Do not pay for CryptoQuant now.
- Do not build a CryptoQuant Stage B lane unless a pre-payment feasibility packet proves:
  1. historical coverage exists for the relevant pre-2025 Stage B period;
  2. data are point-in-time alignable;
  3. licensing/API access supports full reproducible export;
  4. the expected feature family cannot be replicated by free/owned data;
  5. a matched `best_free` vs `best_free_plus_cryptoquant` plan is ready before payment.

---

## 3. Why distinct feature files may produce identical RL behavior

The feature/action audit is the most important clue. Distinct data hashes with identical behavior usually means one of the following.

### 3.1 Evidence-contract failure: feature list not proven

All top audited runs have `feature_list_hash_missing_candidates = 12`.

This does not prove that the wrong features were used. It proves the evidence file cannot prove the exact feature list consumed by the policy. That is a practical audit defect.

Required fix:

```text
Every project3_return_trace_evidence_v1 file must persist:
  feature_list_hash
  ordered_feature_names
  observation_dim
  observation_schema_hash
  input_data_hash
  fitted_transform_hash
  normalizer_hash
  model_checkpoint_hash
```

Without this, the next run can still be questioned.

### 3.2 Observation tensor may not differ enough after preprocessing

Distinct raw or CSV files can collapse after:

```text
normalization
clipping
zero filling
missing-value handling
column intersection
column ordering bugs
feature selection masks
feature drop rules
dtype conversion
NaN/inf sanitization
```

Example failure mode:

```text
variant A has 89 columns
variant B has 108 columns
but agent-multi loads only the intersection with a fixed expected schema,
or clips all new columns into near-constant values,
or the normalizer transforms them into effectively identical tensors.
```

Required diagnostic:

```text
For each top candidate variant, persist:
  raw_feature_hash
  post_feature_selection_hash
  post_scaler_observation_hash
  first_1k_observation_digest
  per-column mean/std/min/max after preprocessing
  nonzero_column_count
  finite_column_count
  dropped_column_list
  added_column_list
```

### 3.3 Policy may be dominated by non-feature state

The environment observation already includes position/equity/unrealized PnL/steps remaining. It is possible that SAC learned a simple state/exposure behavior driven more by:

```text
current position
unrealized PnL
episode progress
forced close effects
cost penalties
action regularity
```

than by price features.

Required diagnostic:

```text
Run feature-ablated inference diagnostics on an already trained policy:
  original features
  zeroed market features
  shuffled market features
  state-only observation if supported
  feature-only observation if supported
```

This is not a Stage C evaluation and should be done only on existing validation traces or pre-held-out diagnostic periods.

If zeroing or shuffling market features barely changes actions, the agent is not using the features.

### 3.4 Action mapping may be insensitive or saturated

Identical action standard deviation across distinct inputs can happen if:

```text
actions are clipped or squashed into a narrow band;
deadband thresholds convert continuous actions into the same trade decisions;
policy output saturates near a fixed target exposure;
position-sizing logic dominates action magnitude;
stop-loss/take-profit logic overrides policy differences;
forced-close mechanics erase action variation near session boundaries.
```

Required diagnostic:

```text
For each top run, persist:
  raw_actor_action
  squashed_action
  clipped_action
  effective_action
  position_target
  position_delta
  trade_executed
  no_trade_reason
  override_reason
  forced_close_trigger
  sltp_trigger
```

If raw actor actions differ but effective actions are identical, the problem is action post-processing. If raw actor actions are identical, the problem is upstream observation/model sensitivity.

### 3.5 Reward may not differentiate feature-driven decisions

If reward heavily penalizes turnover or is dominated by mark-to-market exposure, the policy may learn a generic behavior that ignores feature details.

Required diagnostic:

```text
reward_total
reward_pnl_component
reward_cost_component
reward_turnover_component
reward_drawdown_component
reward_risk_component
reward_forced_close_component
```

Then compare reward components by feature variant. If the reward components are nearly identical, feature differences are not reaching the objective.

### 3.6 Checkpoint/config mapping may be wrong

Distinct candidate names can still accidentally reuse:

```text
same trained checkpoint
same model path
same run_id
same normalized observation file
same policy artifact
same evaluation config
```

Required diagnostic:

```text
model_checkpoint_hash
model_config_hash
run_config_hash
train_data_hash
eval_data_hash
candidate_id
parent_run_id
```

If multiple feature variants reuse a checkpoint without explicit transfer-learning intent, the evidence is invalid for feature comparison.

### 3.7 The differences may simply not matter

This is possible and should not be dismissed. If the entire tested `tech_stat` family is noisy or weak for ETHUSDT 4h under the current reward/action/cost setup, the same policy behavior may be rational. But because `feature_list_hash` is missing and force-close context has not been tested inside live state, this conclusion is premature.

---

## 4. Diagnostics required before another broad GPU matrix

### 4.1 P0 evidence and observation diagnostics

Do this before launching any new training:

```text
1. Persist feature_list_hash in every evidence file.
2. Persist ordered feature names.
3. Persist observation_schema_hash.
4. Persist post-normalization observation digest.
5. Persist model_checkpoint_hash.
6. Persist fitted_transform_hash.
7. Persist action-pipeline diagnostics:
   raw_actor_action
   squashed_action
   clipped_action
   effective_action
   position_delta
   trade_executed
   override_reason
8. Persist reward component decomposition.
9. Persist force-close context fields if present:
   bars_to_force_close
   hours_to_force_close
   is_force_close_zone
   forced_close_triggered
```

Acceptance criteria:

```text
No top candidate evidence file has null feature_list_hash.
Observation hashes differ when feature files differ.
Action-pipeline fields explain where behavior collapses.
Reward components are decomposed enough to diagnose cost/exposure domination.
```

### 4.2 P0 feature perturbation diagnostics

Run inference-only or no-training diagnostics where feasible:

```text
For a trained policy and validation-period trace:
  A. original observation
  B. market features zeroed
  C. market features permuted within time blocks
  D. calendar features zeroed
  E. state variables zeroed if safe
  F. position/equity state only if environment supports it
```

Measure:

```text
mean absolute action delta
effective trade delta
position delta
action entropy
action diversity
turnover delta
reward delta
```

If actions barely change when features are perturbed, the current policy is feature-insensitive.

### 4.3 P0 action-space diagnostics

For the top `ETHUSDT 4h SAC` candidates, compute:

```text
raw_action_mean
raw_action_std
raw_action_entropy
effective_action_mean
effective_action_std
effective_action_entropy
rounded_action_diversity
position_flip_rate
mean_abs_position
fraction_time_in_market
average_holding_period_bars
trade_count_per_episode
cost_to_gross_edge_ratio
```

Acceptance criteria before new training:

```text
raw_action and effective_action both show non-degenerate variation;
effective_action is not always dominated by clipping/deadband/forced-close;
excessive trade flags are explainable by true behavior, not counting bugs.
```

### 4.4 P0 reward diagnostics

Compute per-step reward decomposition:

```text
pnl_reward
cost_penalty
turnover_penalty
drawdown_penalty
exposure_penalty
forced_close_penalty
terminal_reward
```

Acceptance criteria:

```text
Reward is not dominated by one mechanical component.
Feature variants cause measurable reward-component differences if they cause action differences.
Cost penalty is calibrated to realistic execution assumptions.
```

### 4.5 P0 environment force-close diagnostics

Because CSV calendar features did not solve the issue, inspect whether force-close context is available in the live observation state.

Required tests:

```text
1. Observation dictionary contains bars_to_force_close / hours_to_force_close if enabled.
2. These fields are present after wrapper/normalizer transformations.
3. These fields are visible at train and eval time.
4. Values are causal and do not reference future price data.
5. Values change correctly around Friday/session boundaries.
6. Forced-close trigger and observation context are logged in the same trace.
```

If these fail, implement environment-state force-close context as a **new counted diagnostic variant**, not as a silent fix.

---

## 5. Feature and source redesign using free or already owned data

The next feature/source work should be narrower, cleaner, and more interpretable.

### 5.1 Split `tech_stat` into smaller feature families

The current `tech_stat` family is too broad. It mixes many signal types, making it difficult to know whether any subcomponent is useful.

Recommended split:

```text
tech_return:
  return_1, log_return_1, return_5, return_10, return_20, return_60

tech_trend:
  sma/ema ratios, MACD, trend_slope, trend_strength, EMA crosses

tech_momentum:
  RSI, stochastic, Williams %R, CCI, ROC, momentum

tech_volatility:
  ATR/NATR, Bollinger width, historical volatility, realized variance

tech_volume_liquidity:
  OBV, volume ratios, VWAP, MFI

stat_moments:
  rolling mean/std/skew/kurtosis

stat_dependence:
  autocorrelation, squared-return autocorrelation, Hurst proxy

calendar_env_state:
  bars_to_force_close, hours_to_force_close, force-close zone flags
```

Do not launch another broad `tech_stat` rerun until subfamily sensitivity is known.

### 5.2 Build a compact “best_free_v1” family

A pragmatic `best_free_v1` candidate should use already owned/free data:

```text
best_free_v1 =
  compact tech_stat reduced by redundancy
  + jump-robust realized volatility from existing 5m bars
  + train-only regime probabilities
  + train-only OOD score
  + BTC/ETH cross-asset risk state
  + Binance funding/open-interest where already acquired
  + Deribit DVOL if free endpoint provenance is stable
  + ALFRED/FRED point-in-time macro/rates if applicable
```

Do not create a kitchen-sink family. The purpose is to test a clean, economically interpretable signal stack.

### 5.3 Crypto perps

Use free or already acquired perp data first:

```text
funding_rate
funding_rate_zscore
funding_term_structure
open_interest
open_interest_change
premium/basis if available
mark-index divergence if available
```

Binance provides official USDⓈ-M funding-rate history and open-interest market-data endpoints. These are suitable for a free/owned source-family ablation if timestamps and availability are handled correctly.

### 5.4 Crypto volatility

Use Deribit DVOL only if provenance is stable and history covers the Stage B period. Deribit documents a public volatility-index endpoint returning volatility-index candle data and describes volatility indexes as market expectations of future volatility.

Potential features:

```text
btc_dvol
eth_dvol
dvol_realized_vol_spread
crypto_vrp_proxy
dvol_regime
```

### 5.5 Macro and FX

For macro/rates features, use ALFRED/FRED vintage semantics where possible. ALFRED allows retrieval of economic vintages available on a specific historical date, which is the correct anti-leakage model for revised macro data.

Recommended macro/FX source families:

```text
rates_yield_curve_v1
usd_liquidity_proxy_v1
vix_vrp_proxy_v1
fx_carry_v1
fx_value_momentum_v1
```

These should be separate source-family ablations, not silently mixed into `tech_stat`.

### 5.6 Representation learning

Do not add many representation methods simultaneously. Existing LSTM/CNN learned embeddings should first be checked for train-only fitting and evaluated cleanly.

Recommended order:

```text
P0:
  verify existing learned_lstm and learned_cnn were fit train-only;
  if invalid, refit or mark diagnostic-only.

P1:
  TS2Vec_v1 as the first contrastive encoder, because it learns timestamp/subsequence representations through hierarchical contrastive learning.

P2:
  PatchTST / CoST / foundation embeddings only after TS2Vec and existing embeddings are interpreted.
```

### 5.7 Feature selection

Use feature selection as a counted feature-family variant:

```text
tech_stat_reduced_corr_v1
tech_stat_stability_v1
tech_stat_mi_train_only_v1
tech_stat_grouped_permutation_v1
tech_stat_regime_value_v1
```

Rules:

```text
fit selectors on train only;
do not select top-k by validation PnL;
do not use Stage C;
count every selected feature set as a trial in DSR/PBO accounting.
```

---

## 6. How to test force-close / Friday-risk context without changing PPO/SAC/DQN

### 6.1 What has already been tested

CSV calendar/session features were tested and did not produce a Stage B-ready candidate.

That means:

```text
Do not repeat the same CSV calendar diagnostic.
```

### 6.2 What remains untested

The still-untested question is:

```text
Does the policy need force-close context in the live environment state,
alongside position/equity/unrealized_pnl/steps_remaining,
rather than only as CSV features?
```

This distinction matters. Environment state variables are usually treated differently from market features:

```text
state context:
  position
  equity_norm
  unrealized_pnl_norm
  steps_remaining_norm
  bars_to_force_close
  hours_to_force_close

market/context features:
  price indicators
  calendar columns
  regime probabilities
  OOD scores
```

If the forced close is an environment rule, then distance to that rule is arguably environment state, not merely another market feature.

### 6.3 Allowed test design

Add a new counted diagnostic variant:

```text
env_state_force_close_v1:
  bars_to_force_close_norm
  hours_to_force_close_norm
  is_force_close_zone
  is_friday_force_close_bar
```

Constraints:

```text
do not change PPO/SAC/DQN;
do not change optimizer/hyperparameters;
do not touch Stage C;
do not compare to old runs as if only data changed unless the variant is clearly labeled;
count it as a new observation-state variant in the ledger.
```

### 6.4 Required proof before training

Before training, run observation-state unit tests:

```text
1. Field exists in raw env observation.
2. Field survives wrappers.
3. Field survives vectorization.
4. Field survives normalization.
5. Field appears in evidence schema.
6. Field is causal.
7. Field is non-null and finite for all validation rows.
8. Force-close-zone values align with actual forced close events.
```

### 6.5 Minimal force-close diagnostic matrix

Run only if P0 audits confirm the field is missing from live state and should be added.

```text
asset: ETHUSDT
timeframe: 4h
algorithm: SAC
algorithm config: unchanged
stage: Stage B diagnostic only
heldout: locked, no 2025+ rows
seeds: 5 paired seeds minimum
costs:
  base
  plus_50pct
  plus_100pct
```

Variants:

```text
1. baseline_12_env_state_control
2. tech_stat_full_env_state_control
3. tech_stat_reduced_corr_v1_env_state_control
4. tech_stat_reduced_corr_v1_plus_env_force_close_state
```

Optional fifth variant only if the observation audit shows clear signal need:

```text
5. compact_vol_trend_plus_env_force_close_state
```

Rationale:

- `baseline_12_env_state_control` tests whether force-close state helps even without rich features.
- `tech_stat_full_env_state_control` anchors to the current top family.
- `tech_stat_reduced_corr_v1_env_state_control` tests whether a cleaner feature family behaves differently.
- `tech_stat_reduced_corr_v1_plus_env_force_close_state` tests the one currently untested data-presentation gap.
- The compact vol/trend variant is included only if needed, because every variant increases trial burden.

Do not run this matrix if `feature_list_hash` and observation digests are still missing.

---

## 7. Minimal next counted diagnostic matrix

### 7.1 Do not launch immediately

Before any new training, complete this no-GPU/low-GPU audit:

```text
P0A — Evidence contract repair:
  feature_list_hash
  ordered_feature_names
  observation_schema_hash
  post-normalization observation_digest
  model_checkpoint_hash
  fitted_transform_hash

P0B — Action pipeline audit:
  raw_actor_action
  squashed_action
  clipped_action
  effective_action
  position_delta
  override_reason
  trade_executed

P0C — Reward audit:
  pnl component
  cost component
  turnover component
  drawdown/risk component
  forced-close component if present

P0D — Force-close state audit:
  bars_to_force_close / hours_to_force_close in live observation state
```

### 7.2 If no defect or missing state variable is found

If the audit concludes that:

```text
feature lists are correct;
observation tensors differ;
action mapping is correct;
reward decomposition is sane;
force-close context is visible when intended;
```

then do **not** run another ETHUSDT 4h SAC `tech_stat` GPU matrix. The evidence would indicate true feature-family insensitivity or weak signal under the current setup.

Next action in that case:

```text
Close current ETHUSDT 4h SAC tech_stat family as:
  RESEARCH_SIGNAL_WEAK_OR_POLICY_FEATURE_INSENSITIVE

Move to:
  feature/source redesign using best_free_v1,
  compact source-family ablations,
  or a different asset/timeframe family already ranked as economically plausible.
```

### 7.3 If a concrete defect is found

If the audit finds a defect, run only the smallest counted rerun that tests that defect.

Examples:

```text
Defect: feature_list_hash missing only, but observation pipeline correct
Action: repair evidence only; no training rerun required.

Defect: distinct CSV features collapse after normalizer
Action: fix normalizer/schema; rerun 2-variant smoke:
  baseline_12 vs tech_stat_reduced_corr_v1

Defect: action clipping/deadband erases raw policy differences
Action: repair action diagnostics first; do not change action space silently.
  If action mapping must change, count as a new environment/action protocol family.

Defect: force-close context missing from live state
Action: run the force-close diagnostic matrix above.

Defect: reward dominated by costs/turnover
Action: do not modify reward silently.
  Create a new reward-protocol research lane only if user approves it as outside fixed current comparison.
```

---

## 8. What should be killed, repaired, rerun, or deferred

### 8.1 Kill

Kill or close as negative evidence:

```text
1. CSV session-calendar diagnostic as a Stage B promotion path.
   Reason: tested at scale; 0/100 candidate gates; 0 DSR passes.

2. Blind broader ETHUSDT 4h SAC tech_stat rerun.
   Reason: top variants have identical behavior; rerun would likely reproduce same failure.

3. Any candidate with non-positive return, negative Sharpe, no trades, or hard excessive-trade failure unless a concrete data/parameter defect is documented.
   Reason: economic failure, not statistical formality.

4. Any candidate family that fails matched family tests and has no feature/action differentiation.
   Reason: likely data-snooped or feature-insensitive.
```

### 8.2 Repair

Repair before any expensive rerun:

```text
1. Missing feature_list_hash in evidence.
2. Missing observation_schema_hash.
3. Missing post-normalization observation digest.
4. Missing model_checkpoint_hash.
5. Missing action-pipeline decomposition.
6. Missing reward-component decomposition.
7. Missing force-close state context if the environment enforces force-close.
8. Inconsistent cost-scenario naming:
   standardize base, plus_50pct, plus_100pct or map existing pessimistic consistently.
```

### 8.3 Rerun

Rerun only if one of these is true:

```text
1. A concrete evidence/plumbing defect invalidated previous comparison.
2. A live observation-state gap is found and fixed.
3. A compact, pre-registered source/feature family tests a materially new economic hypothesis.
4. A paid-source feasibility packet proves historical, point-in-time aligned data value.
```

Every rerun must be:

```text
counted in ledger;
paired by seed;
run across cost scenarios;
evaluated only on real validation;
excluded from Stage C until gates pass.
```

### 8.4 Defer

Defer:

```text
1. CryptoQuant payment.
2. CryptoQuant Stage B ablation.
3. Broad order-flow/microstructure matrix.
4. TimeGAN/COT-GAN/diffusion synthetic data.
5. LLM trading committee overlays.
6. Specialized open/hold/close hierarchical policies.
7. Reward/action-space redesign, unless explicitly opened as a separate strategy-family research lane.
```

These are not bad ideas. They are bad **next** ideas before the current feature/action insensitivity is diagnosed.

---

## 9. CryptoQuant pre-payment proof requirement

Do not pay for CryptoQuant unless all conditions are met:

```text
1. Historical export/API coverage reaches the relevant pre-2025 training/validation period.
2. Data are point-in-time alignable with timestamps and no future leakage.
3. The vendor/license allows reproducible historical research export.
4. At least one specific feature family is defined before payment:
   exchange_flow_v1
   miner_flow_v1
   stablecoin_flow_v1
   derivatives_risk_v1
5. A free/owned comparator exists:
   best_free_v1
6. The planned test is:
   best_free_v1 vs best_free_plus_cryptoquant_v1
   matched by asset/timeframe/algorithm/seed/cost/split.
7. Payment decision has a kill rule:
   cancel if no marginal value versus best_free_v1.
```

The current 2026-only payload is not enough for Stage B. Paying before historical feasibility is confirmed would be a business error.

---

## 10. Mathematical promotion gates versus research triage metrics

### 10.1 Promotion gates

These are required before Stage C:

```text
DSR_N_raw pass
PBO/CSCV or accepted PBO-lite pass
family Reality Check / SPA not failed
paired seed uncertainty pass
cost scenario pass
trade-behavior gates pass
matched baseline comparison pass
no Stage C contamination
no synthetic validation evidence
no missing evidence contract
```

These are not academic posturing. They prevent paying for false positives after a 5025-trial search surface.

### 10.2 Research triage metrics

These guide the next experiment but do not promote:

```text
diagnostic ranking score
mean return in least-bad table
mean action std
mean exposure
identical action/performance signature
feature hash differences
feature_list_hash missing warning
calendar feature diagnostic result
```

The diagnostic ranking is useful for choosing where to debug. It is not proof of profitability.

---

## 11. Implementation-grade checklist for orchestrator issues

### Issue 1 — Repair evidence contract for feature/action audit

```text
Title:
  Project 3 Stage B — Persist Feature and Observation Hashes in Evidence

Repo:
  agent-multi / financial-data

Priority:
  P0

Do:
  [ ] Add feature_list_hash to every project3_return_trace_evidence_v1 file.
  [ ] Add ordered_feature_names or feature_names_file hash.
  [ ] Add observation_schema_hash.
  [ ] Add raw_input_data_hash.
  [ ] Add post_feature_selection_hash.
  [ ] Add fitted_transform_hash.
  [ ] Add normalizer_hash.
  [ ] Add post_normalization_observation_digest.
  [ ] Add model_checkpoint_hash.
  [ ] Add config_hash and git_commit if missing.
  [ ] Add test: missing feature_list_hash produces warning/blocker, never Stage C pass.

Do not:
  [ ] Do not launch training.
  [ ] Do not touch Stage C.
  [ ] Do not weaken DSR/PBO gates.

Acceptance:
  [ ] Top 12 audited candidates no longer have null feature_list_hash.
  [ ] Evidence can prove exactly which feature list entered policy observation.
```

### Issue 2 — Observation-state force-close audit

```text
Title:
  Project 3 Stage B — Audit Force-Close Context in Live Environment Observation

Repo:
  agent-multi / gym-fx

Priority:
  P0

Do:
  [ ] Inspect whether bars_to_force_close exists in live env observation.
  [ ] Inspect whether hours_to_force_close exists in live env observation.
  [ ] Verify values survive wrappers/vectorization/normalization.
  [ ] Verify values are causal.
  [ ] Verify values align with forced close events.
  [ ] Add evidence fields:
        bars_to_force_close
        hours_to_force_close
        is_force_close_zone
        forced_close_triggered
  [ ] Produce force_close_observation_audit.md/json.

Do not:
  [ ] Do not change PPO/SAC/DQN.
  [ ] Do not use Stage C.
  [ ] Do not silently change observation schema without new variant ID.

Acceptance:
  [ ] Orchestrator can determine whether CSV calendar features were insufficient because force-close context is missing from live state.
```

### Issue 3 — Action pipeline and reward decomposition audit

```text
Title:
  Project 3 Stage B — Diagnose Action Invariance Across Distinct Feature Hashes

Priority:
  P0

Do:
  [ ] Persist raw_actor_action.
  [ ] Persist squashed_action.
  [ ] Persist clipped_action.
  [ ] Persist effective_action.
  [ ] Persist position_delta.
  [ ] Persist trade_executed.
  [ ] Persist no_trade_reason.
  [ ] Persist override_reason.
  [ ] Persist forced_close_trigger.
  [ ] Persist reward components:
        pnl_reward
        cost_penalty
        turnover_penalty
        drawdown_penalty
        risk_penalty
        terminal_reward
  [ ] Compute action entropy / rounded action diversity.
  [ ] Compute position flip rate.
  [ ] Compute forced-close-window exposure.
  [ ] Compare action signatures between:
        tech_stat_full
        plus_session_calendar
        plus_regime_probs
        plus_ood_score
        reduced_corr_v1
        baseline_12

Acceptance:
  [ ] Report identifies whether invariance arises before actor, inside actor, after action clipping, during trade execution, or from reward/cost dominance.
```

### Issue 4 — Close session-calendar CSV diagnostic

```text
Title:
  Close CSV Session-Calendar Diagnostic as NO_STAGE_B_PROMOTION

Priority:
  P0

Do:
  [ ] Record 270/270 done, 0 failed.
  [ ] Record 1220 traces/evidence, 0 failures.
  [ ] Record 0/100 gates, 0/633 DSR_N_raw passes.
  [ ] Mark CSV session-calendar diagnostic as useful negative evidence.
  [ ] Keep Stage C locked.

Acceptance:
  [ ] No one reruns the same CSV calendar matrix blindly.
```

### Issue 5 — Minimal counted force-close rerun packet

```text
Title:
  Prepare Minimal Counted Force-Close Observation-State Diagnostic Matrix

Priority:
  P1, only after Issues 1–3 pass

Precondition:
  [ ] Feature/evidence hashes work.
  [ ] Observation-state audit proves force-close context is missing or not reaching policy.
  [ ] Action/reward audit does not reveal a more fundamental defect.

Matrix:
  asset: ETHUSDT
  timeframe: 4h
  algorithm: SAC
  fixed_config: unchanged
  seeds: 5 paired seeds
  costs: base, plus_50pct, plus_100pct
  variants:
    1. baseline_12_env_state_control
    2. tech_stat_full_env_state_control
    3. tech_stat_reduced_corr_v1_env_state_control
    4. tech_stat_reduced_corr_v1_plus_env_force_close_state
  optional:
    5. compact_vol_trend_plus_env_force_close_state

Rules:
  [ ] Count every run in DSR/PBO ledger.
  [ ] Do not use Stage C.
  [ ] Do not promote from this matrix unless all Stage B gates pass.
```

### Issue 6 — Free/owned source-family redesign

```text
Title:
  Design best_free_v1 Source Family Before Any Paid Data Purchase

Priority:
  P1

Do:
  [ ] Define best_free_v1 feature family:
        compact tech_stat reduced by redundancy
        jump-robust realized volatility
        train-only regime probabilities
        train-only OOD score
        BTC/ETH cross-asset risk state
        Binance funding/OI if available
        Deribit DVOL if stable
        ALFRED/FRED macro/rates if point-in-time
  [ ] Define matched ablations:
        tech_stat_reduced_corr_v1
        best_free_no_perp
        best_free_no_macro
        best_free_no_cross_asset
        best_free_no_regime
  [ ] Define all feature hashes and availability rules.
  [ ] Count as new source-family trials.

Do not:
  [ ] Do not pay CryptoQuant yet.
  [ ] Do not create kitchen_sink_guarded_v2 before compact families are tested.
```

### Issue 7 — CryptoQuant pre-payment feasibility packet

```text
Title:
  CryptoQuant Historical Feasibility Packet Before Payment

Priority:
  P2 / business decision

Do:
  [ ] Confirm historical coverage for pre-2025 Stage B period.
  [ ] Confirm point-in-time timestamps and no leakage.
  [ ] Confirm export/API reproducibility.
  [ ] Define exact feature families before payment.
  [ ] Define best_free_v1 comparator.
  [ ] Define cancellation rule if no marginal Stage B value.

Hard no-go:
  [ ] only recent 2026 coverage available;
  [ ] no reproducible historical export;
  [ ] no matched free comparator;
  [ ] no clear feature family before payment.
```

---

## 12. Reviewer self-critique

### 12.1 What this memo can conclude strongly

It can strongly conclude:

```text
1. Stage C must remain locked.
2. The session-calendar CSV diagnostic did not produce a promotable candidate.
3. Distinct data hashes plus identical action/performance signatures are a serious feature/action sensitivity warning.
4. Missing feature_list_hash is an evidence-contract defect.
5. CryptoQuant should not be paid for until historical feasibility is proven.
6. A broad GPU rerun is currently unjustified.
7. The next work should be observation/evidence/action/reward diagnostics.
```

### 12.2 What this memo cannot prove without repo access

It cannot prove:

```text
1. Whether the observation tensor actually collapses after preprocessing.
2. Whether the same checkpoint was reused accidentally.
3. Whether SAC actor outputs are identical before action post-processing.
4. Whether reward decomposition is dominated by costs or exposure.
5. Whether force-close context in live env state will improve results.
6. Whether best_free_v1 will outperform current tech_stat.
```

Those require the exact artifacts listed in the checklists.

### 12.3 Main risk in my recommendation

The main risk is delaying potentially useful training while auditing infrastructure. I accept that risk because the attached evidence shows a high probability of wasted GPU if the same matrix is repeated. The audit work is smaller than another 270–900 job matrix and directly targets the observed failure mode.

### 12.4 Practical bias

This memo is intentionally biased toward:

```text
short diagnostic cycles;
small counted matrices;
free/owned data first;
evidence plumbing before GPU;
profit after costs over leaderboard metrics;
no paid data without feasibility proof.
```

That is the pragmatic posture for a financial management project.

---

## 13. Final recommendation

The orchestrator should execute this decision:

```text
1. Keep Stage C locked.
2. Close CSV session-calendar diagnostic as NO_STAGE_B_PROMOTION.
3. Do not launch a broad GPU rerun.
4. Repair feature/evidence hashes.
5. Audit observation-state force-close context.
6. Audit action-pipeline and reward decomposition.
7. If a concrete defect is found, run only the minimal counted diagnostic matrix.
8. Redesign feature/source families around compact, free/owned, economically interpretable sources.
9. Do not pay CryptoQuant until a historical feasibility packet passes.
10. Keep every new diagnostic counted in the DSR/PBO ledger.
```

Status:

```text
PROJECT3_STATUS:
  STAGE_B_POST_NO_PROMOTION_DIAGNOSTIC_MODE

STAGE_C:
  LOCKED

NEXT_ACTION:
  FEATURE_ACTION_OBSERVATION_REWARD_AUDIT_BEFORE_GPU
```

---

## 14. References

### Attached project documents used

- `PROJECT3_POST_NO_PROMOTION_AGENT_SPECS_2026_05_14.md`
- `PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md`
- `stage_b_feature_action_audit.md`
- `stage_b_diagnostic_candidate_ranking.md`
- `stage_b_decision_readiness.json`
- `stage_b_post_pragmatic_finalization.md`
- `stageb_dsr_pbo_report.md`
- `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md`
- `31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md`

### External primary / official references

1. Bailey, D. H., and López de Prado, M. **The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.**  
   https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf

2. Bailey, D. H., Borwein, J. M., López de Prado, M., and Zhu, Q. J. **The Probability of Backtest Overfitting.**  
   https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

3. White, H. **A Reality Check for Data Snooping.**  
   https://www.ssc.wisc.edu/~bhansen/718/White2000.pdf

4. Hansen, P. R. **A Test for Superior Predictive Ability.**  
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569

5. Politis, D. N., and Romano, J. P. **The Stationary Bootstrap.**  
   https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf

6. Agarwal, R., Schwarzer, M., Castro, P. S., Courville, A., and Bellemare, M. G. **Deep Reinforcement Learning at the Edge of the Statistical Precipice.**  
   https://arxiv.org/abs/2108.13264

7. Binance Developers. **USDⓈ-M Futures Funding Rate History.**  
   https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History

8. Binance Developers. **USDⓈ-M Futures Open Interest.**  
   https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest

9. Deribit API Docs. **public/get_volatility_index_data.**  
   https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data

10. ALFRED / St. Louis Fed. **Archival FRED.**  
    https://alfred.stlouisfed.org/

11. Yue et al. **TS2Vec: Towards Universal Representation of Time Series.**  
    https://arxiv.org/abs/2106.10466
