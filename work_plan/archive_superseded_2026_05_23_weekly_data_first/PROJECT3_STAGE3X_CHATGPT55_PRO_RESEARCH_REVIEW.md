# Project 3 Stage 3X — ChatGPT 5.5 Pro Web Research Review

**Spec executed:** `ChatGPT 5.5 Pro Web Spec C: Research Review` from `PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md` and `PROJECT3_STAGE3X_CHATGPT55_PRO_RESEARCH_PROMPT_2026_05_14.md`.

**Role:** external senior quant/RL research reviewer.

**Scope:** research memo only. No repository mutation. No training launch. No Stage C access. No PPO/SAC/DQN algorithm implementation changes.

**Date:** 2026-05-15.

---

## 0. Executive decision

The Stage 3X branch is moving in the right pragmatic direction: stop trying to rescue a non-promotable Stage B candidate by running larger GPU matrices, and instead search the **data / feature / preprocessing contract** first. The current artifacts show that Stage C remains denied, no training has been launched by the screening workers, broad GPU work is blocked, and only a small SAC smoke plan is allowed after train/validation-only CPU screening. The current target-relation screen processed 54 genomes, passed 13 CPU-screen candidates, and selected 12 contracts. That is a reasonable first reduction of the search space.

However, the CPU screen is **not sufficient for broad GPU work or DEAP/NSGA-II optimization**. It is sufficient only for a **small counted SAC smoke matrix** whose purpose is to test whether the selected contracts produce non-degenerate policy behavior and valid evidence traces. The first GPU objective must not be profit maximization yet. The first GPU objective is: prove that the contracts change the observation tensor, produce distinguishable action distributions, avoid no-trade / overtrade collapse, and create complete evidence with `feature_list_hash`, `observation_state_hash`, trades, profit, and Stage C denial.

The selected contracts are plausible, but they are concentrated around BTC/BTC perpetual, learned CNN/LSTM representations, and one AUDUSD FX candidate. That is acceptable for a smoke test, not for a broad claim about assets or features. The BTC perpetual 4h `crypto_full` and `kitchen_sink_guarded` contracts have identical screen scores, IC, proxy return, and trade count; both should not be launched blindly unless the orchestrator explicitly wants a duplicate-family check. One should be primary and the other should be a counted redundancy test or deferred.

The next practical decision should be:

```text
ALLOW: small counted SAC smoke plan, maximum 4–6 contracts, 3 seeds, base cost only, Stage C denied.
BLOCK: broad GPU rerun, Stage C, paid CryptoQuant, synthetic rescue, PPO/DQN expansion, and NSGA-II hyperparameter evolution until smoke behavior passes.
```

---

## 1. Source facts used from the attached spec kit

The active Stage 3X spec kit states that the project is now in a **SAC-first actor-critic input optimization** branch. The intended sequence is: screen data/feature/preprocessing contracts on train/validation only; use DEAP/NSGA-II only after the CPU filter reduces the search space; optimize SAC hyperparameters per surviving contract; keep PPO/DQN as robustness comparators; and keep Stage C locked until Stage B promotion.

The same spec kit records the current facts to verify: Stage C access is denied; Stage B has no promotion-ready candidate; broad GPU launch is blocked by `NO_STAGE_B_PROMOTION`; the parametric data-space worker discovered 369 train-only input datasets and emitted 54 CPU-screening genomes; the target-relation screen passed 13 and selected 12 contracts; and the guard allows only a small SAC smoke plan, not broad GPU launch.

The parametric search-space summary confirms that Stage C access is denied, training was not launched, 369 input datasets were discovered, 20 assets are available, 3 timeframes are included, 10 feature presets exist, and 54 CPU-screening seed genomes were emitted. The schema also defines the search surface: assets, timeframes, source families, feature presets, feature selection methods, preprocessing profiles, representation methods, SAC learning rates, batch sizes, entropy coefficients, gamma, tau, and seasonal contexts.

The target-relation screen confirms that Stage C access was denied, training was not launched, 54 genomes were screened, 13 passed the CPU screen, and 12 contracts were selected. The highest-ranked contracts are BTCUSDT perpetual 4h `crypto_full` / `kitchen_sink_guarded` with `regime_conditioned_topk`, BTCUSDT 1h/4h learned CNN and learned LSTM contracts, and AUDUSD 4h/1h FX contracts.

The absurdity guard confirms that broad GPU launch is still blocked, a small SAC smoke is allowed, selected feature contracts are 12, and the blocking issue remains `NO_STAGE_B_PROMOTION`.

The Stage B feature/action audit remains an important warning: among 12 audited top candidates, all were missing `feature_list_hash`, all had distinct data hashes, and 11 top `tech_stat` variants had identical action/trade/performance signatures. Therefore, any new Stage 3X smoke must require non-null `feature_list_hash` and `observation_state_hash`, and must explicitly check that different input contracts actually change the observation and action behavior.

---

## 2. Reviewer verdict on the CPU screen

### 2.1 Is the CPU screen sufficient before SAC smoke testing?

**Yes, but only for a small smoke test.**

The CPU screen is sufficient to justify a limited SAC smoke plan because it already applies the correct high-level constraints:

```text
1. Stage C access is DENIED.
2. Training was not launched by the screen.
3. The search surface is contract-level, not model-only.
4. The screen reduces 54 genomes to 12 selected contracts.
5. High-IC contracts with negative cost-aware proxy return are now blocked.
6. The absurdity guard allows only small SAC smoke, not broad GPU.
```

This is pragmatic. It avoids spending GPU on obviously bad contracts while not pretending that a CPU proxy is evidence of tradability.

### 2.2 Is the CPU screen sufficient before DEAP/NSGA-II?

**No.**

DEAP/NSGA-II should not start immediately after this CPU screen. It should start only after the first SAC smoke matrix proves:

```text
1. Every generated SAC config denies Stage C.
2. Every trial has a non-null feature_list_hash.
3. Every trial has a non-null observation_state_hash.
4. Observation tensors differ when selected contracts differ.
5. Action distributions differ enough to rule out plumbing collapse.
6. No selected contract collapses to no-trade.
7. No selected contract triggers excessive-trade hard failure.
8. Return traces and evidence files are complete.
9. Base-cost smoke result is not obviously dominated by a simple baseline.
```

If these are not true, NSGA-II would optimize around a broken pipeline or a degenerate reward/action mapping.

### 2.3 What the current CPU screen still misses

The current CPU screen is directionally useful, but incomplete. It should not be interpreted as a complete forecast of RL performance.

Missing or under-specified checks:

```text
1. Observation tensor hash comparison:
   verifies that contract differences reach the actual SAC observation.

2. Feature-list hash comparison:
   verifies that selected columns are explicit and reproducible.

3. Action-sensitivity proxy:
   verifies that small observation perturbations would not be swallowed by scaling/action squashing/deadband.

4. Regime-wise proxy return:
   verifies that proxy edge is not concentrated in one tiny regime.

5. Trade-rate feasibility:
   verifies that proxy thresholding does not imply impossible turnover.

6. Cost-to-gross-edge sanity:
   verifies that expected trading cost does not consume most of the proxy edge.

7. Train/validation rank stability:
   verifies that the selected features are not train-only artifacts.

8. Cross-contract redundancy:
   detects near-duplicate contracts, such as `crypto_full` and `kitchen_sink_guarded` returning identical CPU scores.
```

---

## 3. Review of the selected contracts

## 3.1 Top 12 selected contracts

| Rank | Contract | Reviewer decision |
|---:|---|---|
| 1 | `btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00` | **Primary smoke candidate.** Strongest IC/proxy result, 4h, perp source family likely valuable. |
| 2 | `btcusdt_perp__4h__kitchen_sink_guarded__regime_conditioned_topk__p00` | **Duplicate-family caution.** Same score/IC/proxy/trades as rank 1; smoke only if the goal is to test whether kitchen-sink adds anything over crypto_full. |
| 3 | `btcusdt__1h__learned_cnn__rank_ic_topk__p00` | **Primary smoke candidate.** Learned CNN, high proxy return, 1h. Useful representation-family test. |
| 4 | `btcusdt__1h__learned_cnn__regime_conditioned_topk__p00` | **Secondary.** Similar to rank 3; use only if comparing rank-IC vs regime-conditioned selection. |
| 5 | `btcusdt__4h__learned_cnn__rank_ic_topk__p00` | **Primary smoke candidate.** 4h learned CNN counterpart to rank 3. |
| 6 | `btcusdt__4h__learned_cnn__regime_conditioned_topk__p00` | **Secondary.** Useful if smoke budget includes selector comparison. |
| 7 | `btcusdt__4h__learned_cnn__corr_stability_topk__p00` | **Defer initially.** Same asset/preset as ranks 5–6, weaker proxy. Use after rank/regime selectors if needed. |
| 8 | `btcusdt__1h__learned_lstm__regime_conditioned_topk__p00` | **Primary or secondary.** Useful as learned-LSTM comparison against learned-CNN. |
| 9 | `btcusdt__1h__learned_lstm__rank_ic_topk__p00` | **Defer or pair with rank 8.** Same proxy as rank 8; choose one first. |
| 10 | `audusd__4h__fx_full__corr_stability_topk__p00` | **Primary smoke candidate.** Only strong FX diversification candidate. |
| 11 | `audusd__1h__fx_full__corr_stability_topk__p00` | **Secondary.** Low proxy return; useful only if FX smoke budget permits. |
| 12 | `btcusdt__1h__learned_lstm__corr_stability_topk__p00` | **Defer.** Weaker than ranks 8–9. |

### 3.2 Recommended first smoke subset

The first smoke subset should be small and diverse. I recommend **five contracts**, not all twelve:

```text
S1: btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00
S2: btcusdt__1h__learned_cnn__rank_ic_topk__p00
S3: btcusdt__4h__learned_cnn__rank_ic_topk__p00
S4: btcusdt__1h__learned_lstm__regime_conditioned_topk__p00
S5: audusd__4h__fx_full__corr_stability_topk__p00
```

Optional sixth contract only if the orchestrator wants an explicit redundancy test:

```text
S6: btcusdt_perp__4h__kitchen_sink_guarded__regime_conditioned_topk__p00
```

Why not all twelve immediately?

```text
1. Several contracts are near-duplicates by asset/preset/method.
2. GPU budget should test diversity first, not minor selector variants.
3. The previous Stage B feature/action audit showed distinct feature hashes can still produce identical behavior.
4. Every smoke run is a counted trial, so unnecessary variants increase the DSR/PBO burden later.
```

### 3.3 Why ETHUSDT 4h is not the first Stage 3X smoke target

The prior pragmatic branch had focused on `ETHUSDT 4h + SAC + tech_stat`, but the new CPU target-relation screen selected mostly BTC/BTC perpetual and AUDUSD contracts. This does not mean ETH is worthless. It means the current train/validation CPU proxy did not rank ETH contracts among the selected Stage 3X contracts.

The pragmatic decision is:

```text
Do not force ETHUSDT 4h into the first Stage 3X smoke unless the orchestrator explicitly wants a continuity baseline.
```

A continuity baseline can be useful, but it should be labeled as such:

```text
S0_CONTINUITY: ethusdt_4h_sac_tech_stat_reduced_corr_or_full
```

It should not displace the top CPU-screened contracts if the purpose is Stage 3X input optimization.

---

## 4. Additional cheap data/feature sanity checks before GPU

The next worker should add the following CPU-only checks before any smoke plan is emitted. These checks are cheap compared with SAC and will prevent wasting GPU on degenerate contracts.

### 4.1 Rank IC variants

The current screen uses rank IC-style diagnostics, but the orchestrator should require a richer IC panel.

Required IC variants:

```text
1. Spearman IC to forward return at horizons:
   h = 1, 2, 3, 6, 12 bars.

2. Spearman IC to future volatility-adjusted return:
   forward_return_h / trailing_volatility.

3. IC sign stability across contiguous train folds.

4. IC sign stability across validation folds.

5. Rank IC by regime:
   low-vol, high-vol, trend, chop, high-volume / low-volume if available.

6. IC decay curve:
   IC(h=1), IC(h=2), IC(h=3), IC(h=6), IC(h=12).
```

Acceptance policy:

```text
PASS if:
  best_abs_IC is positive and stable enough,
  validation IC sign is not opposite train IC,
  proxy return remains positive after cost sanity.

WARN if:
  IC exists only at one horizon,
  IC is high but proxy return is tiny,
  IC is concentrated in one short regime.

FAIL if:
  train IC is high but validation IC flips sign,
  high IC contract has negative cost-aware proxy return,
  IC is caused by a tiny number of bars/trades.
```

### 4.2 Mutual information

Mutual information should remain a **screening diagnostic**, not a feature-promotion proof. Use `mutual_info_regression` or a deterministic fallback. Scikit-learn documents mutual information as a non-negative dependency measure and implements a nonparametric estimator based on k-nearest-neighbor entropy estimation.

Required MI checks:

```text
MI(feature_t, forward_return_{t+h})
MI(feature_t, sign(forward_return_{t+h}))
MI(feature_t, future_realized_volatility_{t+h})
MI(feature_t, future_cost_adjusted_proxy_reward)
```

Engineering policy:

```text
- Fit or compute only on train/validation, never Stage C.
- Report MI rank stability across contiguous folds.
- Do not select final top-k by validation MI alone.
- Treat high MI with unstable IC as suspicious.
```

### 4.3 Regime-conditioned value

The selected top contracts include `regime_conditioned_topk`, so regime diagnostics must be explicit.

Required regime report:

```text
for each selected contract:
  n_bars_by_regime
  n_proxy_trades_by_regime
  proxy_return_by_regime
  cost_adjusted_proxy_return_by_regime
  IC_by_regime
  turnover_by_regime
  drawdown_proxy_by_regime
```

No smoke candidate should pass if the reported edge exists only in an extremely small regime unless that regime is explicitly the purpose of the strategy and has enough samples.

### 4.4 Turnover and cost sanity

The previous Stage B reports showed excessive-trading and no-trade pathologies. Therefore, CPU proxy contracts must include a rough turnover/cost sanity check before SAC.

Required fields:

```text
proxy_trades
proxy_trades_per_year
proxy_avg_holding_bars
proxy_turnover_per_bar
proxy_cost_paid
proxy_gross_edge
proxy_cost_to_gross_edge_ratio
proxy_net_edge
```

Hard CPU rejection:

```text
proxy_net_edge <= 0
proxy_cost_to_gross_edge_ratio >= 1.0
proxy_avg_holding_bars < 1 unless explicitly scalping with a valid execution model
proxy_trades too small to estimate, e.g. < 10 total trades, unless contract is only exploratory
```

For the current top contracts, the rank 1 and rank 2 BTC perpetual 4h candidates have only 14 proxy trades. That is not automatically bad, but it is a **low-sample warning**. The smoke should verify whether SAC learns stable behavior or simply overfits a sparse proxy.

### 4.5 Leakage guards

Required leakage checks:

```text
1. Stage C firewall:
   no DATE_TIME >= 2025-01-01 in fitting, scaling, feature selection, CPU screening, or smoke training.

2. Action timing:
   max_input_timestamp <= decision_timestamp.

3. Scaling:
   scalers fit on train only;
   rolling scalers use trailing windows only;
   expanding scalers do not peek into validation.

4. Feature selection:
   top-k selected without Stage C;
   validation only used as declared CPU screen, not hidden target tuning.

5. Rolling features:
   no centered windows;
   no backfilled warmup values from the future.

6. Learned representations:
   encoders must be fit train-only for the specific split or clearly marked as invalid for decision-grade smoke.

7. Cross-source data:
   macro/on-chain/perp features require availability timestamps, not just observation timestamps.
```

### 4.6 Feature redundancy and stability

Required redundancy/stability checks:

```text
1. near_constant_count
2. high_missingness_count
3. correlation_cluster_count
4. selected_feature_redundancy_ratio
5. feature_rank_stability_train_folds
6. feature_rank_stability_validation_folds
7. selected_feature_family_mix
8. max_single_family_concentration
```

A contract with 64 features all drawn from one highly correlated family should be penalized versus a smaller, more diverse, stable set.

### 4.7 Observation plumbing checks before smoke

Because the Stage B feature/action audit found missing feature hashes and identical behavior across distinct data hashes, the following checks are mandatory:

```text
1. selected_feature_list is non-empty.
2. feature_list_hash is non-null and deterministic.
3. observation_state_hash is non-null and deterministic.
4. observation_tensor_digest differs across distinct selected contracts.
5. observation tensor has finite values after preprocessing.
6. preprocessing profile is preserved in the emitted SAC config.
7. seasonal_context is preserved in the emitted SAC config.
8. force_close_obs, if selected, appears in live environment state, not just a CSV feature file.
```

If two distinct contracts produce identical observation tensor digests, run no SAC smoke for both; repair the pipeline first.

---

## 5. Preprocessing search review

The schema exposes these preprocessing profiles:

```text
p00_current_contract
p01_no_scaling_control
p02_rolling_short_64
p03_rolling_long_512
p04_expanding_zscore
p05_clip_tight_5
p06_wide_observation_64
```

### 5.1 Recommended interpretation

| Profile | Use | Reviewer view |
|---|---|---|
| `p00_current_contract` | Baseline continuity. | Keep as required control. |
| `p01_no_scaling_control` | Detect whether scaling is dominating behavior. | Useful smoke diagnostic, but likely unstable. |
| `p02_rolling_short_64` | Adapts to regime changes quickly. | Good for 1h/15m; may be noisy. |
| `p03_rolling_long_512` | More stable rolling normalization. | Good default candidate. |
| `p04_expanding_zscore` | Stable train/online normalization. | Useful but risks slow adaptation. |
| `p05_clip_tight_5` | Controls outliers. | Good for SAC stability; can destroy tail information if too aggressive. |
| `p06_wide_observation_64` | Wider temporal context. | Useful but increases observation dimension and overfit risk. |

### 5.2 Pragmatic smoke policy

For the first smoke matrix, do not search all preprocessing profiles for every contract. Use:

```text
primary: p03_rolling_long_512
control: p00_current_contract
optional: p05_clip_tight_5 if NaN/outlier diagnostics are problematic
```

The first smoke should answer whether the data contracts are alive, not optimize every preprocessing knob.

### 5.3 Train/validation split policy

Required:

```text
1. Fit scalers on train only.
2. Apply scaler to validation without refit.
3. Rolling scalers use only historical observations at each timestamp.
4. Feature selectors are fit only within allowed train/validation CPU screen logic.
5. Stage C remains fully inaccessible.
6. Every feature selector/preprocessor emits fit_start, fit_end, and used_validation_for_selection flag.
```

For CPU-screening, it is acceptable to use validation as the screening target **only if** every selected contract is treated as a counted trial and no Stage C is touched. It is not acceptable to later pretend the selected contracts were purely train-only.

---

## 6. SAC-first hyperparameter optimization after smoke passes

### 6.1 SAC search should not begin until smoke passes

SAC hyperparameter evolution should begin only if the smoke plan passes these gates:

```text
1. no Stage C access;
2. complete return/evidence traces;
3. non-null feature_list_hash and observation_state_hash;
4. no no-trade collapse;
5. no excessive-trade hard flag;
6. no always-in-market losing flag;
7. at least one selected contract beats a matched baseline under base cost;
8. action distributions differ meaningfully across contracts;
9. smoke results are logged as counted trials.
```

### 6.2 Safe SAC hyperparameters to search

The current schema already includes a conservative SAC search surface:

```text
sac_learning_rate: [3e-05, 1e-04, 3e-04]
sac_batch_size: [128, 256, 512]
sac_ent_coef: ['auto', 0.005, 0.01, 0.03]
sac_gamma: [0.97, 0.99, 0.995]
sac_tau: [0.002, 0.005, 0.01]
```

These are reasonable. Stable-Baselines3’s SAC defaults are close to `learning_rate=3e-4`, `buffer_size=1_000_000`, `batch_size=256`, `tau=0.005`, `gamma=0.99`, and `ent_coef='auto'`, so the schema covers a sensible region around the common default.

### 6.3 Recommended first DEAP/NSGA-II SAC range

For the first DEAP population, use the schema ranges exactly. Do not expand yet.

```yaml
sac_learning_rate:
  type: categorical_or_log_choice
  values: [0.00003, 0.0001, 0.0003]
  recommendation: start with 0.0001 and 0.0003 as most likely useful

sac_batch_size:
  type: categorical
  values: [128, 256, 512]
  recommendation: prefer 256; 512 only if replay buffer diversity is adequate

sac_ent_coef:
  type: categorical
  values: ['auto', 0.005, 0.01, 0.03]
  recommendation: prefer 'auto'; fixed values are diagnostic

sac_gamma:
  type: categorical
  values: [0.97, 0.99, 0.995]
  recommendation:
    15m/1h: 0.99 or 0.995
    4h: 0.97 or 0.99 if horizon is shorter / costs matter

sac_tau:
  type: categorical
  values: [0.002, 0.005, 0.01]
  recommendation: prefer 0.005 default; 0.002 for smoother target updates
```

### 6.4 Optional SAC parameters after the first DEAP population

Only after smoke and first DEAP generation are stable, consider adding:

```text
buffer_size: [200_000, 500_000, 1_000_000]
learning_starts: [5_000, 10_000, 25_000]
train_freq: [1, 4]
gradient_steps: [1, 4]
policy_hidden_layers: [(128,128), (256,256)]
```

Do **not** add these in the first generation unless compute is abundant. Too many hyperparameters will make the optimization look active while actually expanding false-discovery risk.

### 6.5 SAC parameters to avoid changing in Stage 3X

Avoid searching these until evidence improves:

```text
action space semantics
reward function definition
position sizing rules
episode termination rules
PPO/DQN implementation internals
SAC algorithm source code
target entropy formulas beyond 'auto' vs fixed ent_coef diagnostics
```

Changing these would move Project 3 from input optimization into model/environment redesign. That may be a future project, but it is outside this spec.

---

## 7. DEAP/NSGA-II configuration recommendation

NSGA-II is appropriate because the project has competing objectives: return, cost, turnover, robustness, simplicity, and statistical credibility. Deb et al. introduced NSGA-II as a fast elitist nondominated sorting genetic algorithm for multi-objective optimization, and DEAP provides NSGA-II tooling through `selNSGA2` and related operators.

### 7.1 First DEAP population size

Do not start with a large population. Use:

```text
population_size: 16 or 24
n_generations_initial: 3
max_total_gpu_trials_first_pass: 48 to 72
seeds_per_candidate_initial: 3
cost_scenario_initial: base only
```

After the first pass, promote only Pareto-front candidates that pass trade/evidence gates into a stricter validation plan:

```text
seeds: 5 minimum, 10 preferred
costs: base, plus_50pct, plus_100pct
PBO/DSR/family tests: required before Stage B promotion discussion
```

### 7.2 Genome structure for first DEAP population

```yaml
genome:
  data_contract_id: selected_contract_id
  preprocessing_profile: [p00_current_contract, p03_rolling_long_512, p05_clip_tight_5]
  feature_budget: [8, 12, 16, 24, 32]
  representation_method: [raw_selected, pca, autoencoder]
  seasonal_context: [off, force_close_obs]
  sac_learning_rate: [3e-05, 1e-04, 3e-04]
  sac_batch_size: [128, 256, 512]
  sac_ent_coef: ['auto', 0.005, 0.01, 0.03]
  sac_gamma: [0.97, 0.99, 0.995]
  sac_tau: [0.002, 0.005, 0.01]
```

Recommendation: keep `contrastive_timeseries` out of the first DEAP population unless a contrastive representation artifact is already verified train-only and evidence-compatible. Otherwise it creates a new representation research lane inside a hyperparameter optimizer.

### 7.3 Avoid too many objectives

NSGA-II performs better when objectives are meaningful and not too numerous. Do not throw 15 noisy objectives into the first population.

Use **hard constraints** for non-negotiable requirements and **4–6 objectives** for trade-offs.

Hard constraints:

```text
stage_c_access == DENIED
feature_list_hash_present == true
observation_state_hash_present == true
return_trace_present == true
no_no_trade_collapse == true
no_excessive_trade_hard_flag == true
no_always_in_market_losing_flag == true
base_cost_evidence_present == true
```

Primary objectives:

```text
maximize net_return_after_cost
maximize downside_adjusted_return / Sortino-like score
minimize max_drawdown
minimize turnover / trade_rate_penalty
maximize seed_stability_proxy
minimize feature_complexity
```

Optional penalties, not separate objectives in generation 1:

```text
DSR_penalty
PBO_penalty
family_test_penalty
Friday_exposure_penalty
proxy_to_RL_disagreement_penalty
```

### 7.4 Practical objective definitions

```text
objective_1_net_return:
  median validation net return across 3 smoke seeds.

objective_2_downside:
  median Sortino or negative downside deviation.

objective_3_drawdown:
  negative max drawdown, or penalty if drawdown > threshold.

objective_4_trade_sanity:
  negative penalty for excessive trades, cost_to_gross_edge_ratio, no-trade.

objective_5_seed_stability:
  negative inter-seed dispersion or positive paired win rate vs baseline.

objective_6_simplicity:
  negative feature count, negative preprocessing complexity, negative source cost.
```

Do not use DSR as a first-generation objective if only 3 smoke seeds and base cost are available. Use DSR as a **promotion gate** after enough evidence exists.

---

## 8. Feature and source-family recommendations

### 8.1 Technical/statistical families

Split noisy large feature sets into smaller families:

```text
return
trend
momentum
volatility
volume_liquidity
rolling_moments
autocorrelation_dependence
regime_flags
```

The previous Stage B audit showed that broad `tech_stat` variants can produce identical action signatures. This suggests the policy may be insensitive to many feature differences or that the feature/action path is not sufficiently verified. Smaller families make failures interpretable.

### 8.2 Crypto spot and perp families

For crypto, prioritize owned/free data:

```text
crypto_spot_ohlcv
crypto_perp_funding
open_interest
basis / premium index
realized volatility
jump-robust realized volatility
BTC/ETH relative strength
cross-asset correlation
```

Binance official docs provide funding-rate history and open-interest endpoints. These are practical low-cost sources for the perp/funding family.

### 8.3 Crypto volatility and VRP

Use free Deribit volatility-index data only if provenance and historical coverage are stable. Deribit documents an endpoint for volatility-index candle data and describes volatility indexes as market expectations of future volatility.

Do not pay for CryptoQuant until a pre-payment proof demonstrates:

```text
1. historical coverage across the relevant Stage B period;
2. point-in-time alignment;
3. feature uniqueness versus free/owned sources;
4. train/validation CPU-screen utility;
5. incremental value in a matched free-vs-free-plus-paid trial;
6. realistic cancellation/payback threshold.
```

### 8.4 FX and macro

For FX, prioritize:

```text
carry / rate differential
momentum
value / PPP proxy
session-aware volatility
COT positioning if available
macro release/vintage data when point-in-time aligned
```

ALFRED is the correct pattern for revised macro data because it supports historical data vintages available on a specific date. Do not use revised macro values without vintage/availability timestamps.

### 8.5 Calendar/session and force-close context

CSV calendar features were tested and did not produce a Stage B-ready candidate in the prior branch. That does not prove calendar context is useless. It means the CSV feature presentation did not solve the problem.

The remaining test is environment-state force-close context:

```text
bars_to_force_close
hours_to_force_close
is_force_close_window
session_age
session_remaining
```

These should be live observation-state fields, not just columns in a feature CSV. The prior audit specifically suggested that live observation context may be missing even if CSV calendar features exist.

---

## 9. What should be killed or deferred

### 9.1 Kill now

```text
1. Any selected contract with Stage C rows in fit/selection/smoke data.
2. Any contract without feature_list_hash.
3. Any emitted SAC config without observation_state_hash.
4. Any smoke candidate with no-trade collapse.
5. Any smoke candidate with excessive-trade hard flag.
6. Any smoke candidate with always-in-market losing behavior.
7. Any high-IC contract with negative cost-aware proxy return.
8. Any paid-data lane without pre-payment proof.
9. Any broad GPU matrix while the absurdity guard blocks broad GPU launch.
10. Any Stage C access request.
```

### 9.2 Defer

```text
1. Full DEAP/NSGA-II until the first SAC smoke matrix passes evidence and behavior gates.
2. PPO/DQN robustness comparisons until SAC smoke produces at least one non-degenerate contract.
3. CryptoQuant historical/API payment until a pre-payment proof exists.
4. TimeGAN/COT-GAN/diffusion synthetic lanes until Phase 4 entry conditions are satisfied.
5. LLM TradingAgents overlay until a real Stage B candidate has interpretable evidence.
6. Order-book/order-flow paid sources until execution/cost modeling is validated.
7. Contrastive representation search unless train-only artifacts already exist and are evidence-compatible.
```

### 9.3 Repair before more GPU

```text
1. feature_list_hash missing in evidence;
2. observation_state_hash missing in evidence;
3. distinct data hashes producing identical action signatures;
4. force-close context absent from live observation state;
5. cost scenario inconsistency between base/pessimistic and plus_50pct/plus_100pct;
6. trade-rate annualization anomalies.
```

---

## 10. Minimal next counted diagnostic matrix

### 10.1 Smoke matrix objective

The next matrix is not a Stage B promotion matrix. It is a **smoke matrix** to verify that selected data/preprocessing contracts produce valid, non-degenerate SAC behavior.

### 10.2 Recommended matrix

```yaml
stage: stage3x_sac_smoke
stage_c_access: DENIED
training_scope: small_smoke_only
algorithm: SAC
ppo_dqn: not_in_first_smoke
seeds: [0, 1, 2]
cost_scenarios: [base]
return_trace: required
evidence: required
feature_list_hash: required
observation_state_hash: required
```

Contracts:

```text
1. btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00
2. btcusdt__1h__learned_cnn__rank_ic_topk__p00
3. btcusdt__4h__learned_cnn__rank_ic_topk__p00
4. btcusdt__1h__learned_lstm__regime_conditioned_topk__p00
5. audusd__4h__fx_full__corr_stability_topk__p00
```

Optional redundancy check:

```text
6. btcusdt_perp__4h__kitchen_sink_guarded__regime_conditioned_topk__p00
```

Preprocessing:

```text
primary: p03_rolling_long_512
control: p00_current_contract for one or two contracts only
optional: p05_clip_tight_5 if outlier/NaN checks flag instability
```

Seasonal context:

```text
primary: off
specific diagnostic: force_close_obs for the 4h contracts only if live observation-state support is implemented and hashed
```

### 10.3 Smoke pass criteria

A contract passes smoke only if all hard gates pass:

```text
1. Stage C denied.
2. No training rows at/after 2025-01-01.
3. Feature-list hash present.
4. Observation-state hash present.
5. Return trace present.
6. Evidence file present.
7. No no-trade collapse.
8. No excessive-trade hard flag.
9. No always-in-market losing flag.
10. Net return not obviously dominated by matched simple baseline under base cost.
11. Action distribution is not identical to another distinct contract unless explicitly expected.
12. Trade count is plausible for timeframe.
```

### 10.4 Smoke fail criteria

Fail and stop escalation if:

```text
1. Two or more distinct contracts produce identical observation hashes.
2. Two or more distinct contracts produce identical action signatures again.
3. Most contracts no-trade or overtrade.
4. Force-close observation state does not appear in the live environment digest.
5. Evidence lacks hashes or trace artifacts.
6. Costs are missing or inconsistent.
```

If these happen, the next work is pipeline repair, not more SAC or NSGA.

---

## 11. Concrete GitHub issue checklist

```text
Title:
  Project 3 Stage 3X — ChatGPT 5.5 Pro Research Review Integration

Scope:
  Integrate the Stage 3X research review into the orchestrator plan.
  Do not launch broad GPU work. Do not unlock Stage C. Do not modify PPO/SAC/DQN algorithms.

P0 — CPU-screen hardening before smoke:
  [ ] Add observation_tensor_digest to selected contracts if missing.
  [ ] Require non-null feature_list_hash before smoke config emission.
  [ ] Require non-null observation_state_hash before smoke config emission.
  [ ] Add rank IC horizon panel: h=1,2,3,6,12 bars.
  [ ] Add validation IC sign-stability report.
  [ ] Add MI rank report using sklearn mutual_info_regression or deterministic fallback.
  [ ] Add regime-conditioned IC/proxy-return report.
  [ ] Add proxy cost-to-gross-edge ratio.
  [ ] Add proxy average holding period and trades/year sanity.
  [ ] Add cross-contract redundancy report.
  [ ] Fail contracts with Stage C rows.
  [ ] Fail contracts with negative cost-aware proxy return.

P0 — Smoke config guardrails:
  [ ] Emit only SAC configs.
  [ ] Use 3 smoke seeds by default.
  [ ] Use base cost only for smoke.
  [ ] Preserve selected feature columns.
  [ ] Preserve preprocessing_profile.
  [ ] Preserve seasonal_context.
  [ ] Deny Stage C in every config.
  [ ] Enable return_trace and evidence output.
  [ ] Include feature_list_hash and observation_state_hash.
  [ ] Include progress, trades, profit, no-trade, excessive-trade, and always-in-market flags.
  [ ] Confirm smoke-plan tool does not launch training.

P0 — Recommended first smoke contracts:
  [ ] btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00
  [ ] btcusdt__1h__learned_cnn__rank_ic_topk__p00
  [ ] btcusdt__4h__learned_cnn__rank_ic_topk__p00
  [ ] btcusdt__1h__learned_lstm__regime_conditioned_topk__p00
  [ ] audusd__4h__fx_full__corr_stability_topk__p00
  [ ] Optional redundancy: btcusdt_perp__4h__kitchen_sink_guarded__regime_conditioned_topk__p00

P1 — After smoke passes:
  [ ] Start DEAP/NSGA-II only on smoke-passing contracts.
  [ ] Use SAC learning_rate in [3e-05, 1e-04, 3e-04].
  [ ] Use SAC batch_size in [128, 256, 512].
  [ ] Use SAC ent_coef in ['auto', 0.005, 0.01, 0.03].
  [ ] Use SAC gamma in [0.97, 0.99, 0.995].
  [ ] Use SAC tau in [0.002, 0.005, 0.01].
  [ ] Keep DEAP population size <= 24 for first pass.
  [ ] Keep first pass generations <= 3.
  [ ] Count every GPU trial in the ledger.
  [ ] Preserve Stage C denial evidence.

P1 — Multi-objective score design:
  [ ] Objective: maximize net return after base cost.
  [ ] Objective: maximize downside-adjusted return.
  [ ] Objective: minimize max drawdown.
  [ ] Objective: minimize turnover/trade-rate penalty.
  [ ] Objective: maximize seed stability / reduce seed dispersion.
  [ ] Objective: minimize feature/source complexity.
  [ ] Hard constraint: no no-trade collapse.
  [ ] Hard constraint: no excessive-trade hard flag.
  [ ] Hard constraint: no always-in-market losing flag.
  [ ] Hard constraint: evidence files complete.

P2 — Defer:
  [ ] No broad GPU matrix before smoke passes.
  [ ] No PPO/DQN robustness expansion before SAC smoke passes.
  [ ] No Stage C.
  [ ] No CryptoQuant payment without pre-payment proof.
  [ ] No synthetic Phase 4 training until real-data evidence packet exists.
  [ ] No LLM/TradingAgents overlay until at least one real Stage B candidate is credible.
```

---

## 12. Required acceptance outputs for the orchestrator

The orchestrator should require the next agent handoff to produce:

```text
1. stage3x_cpu_screen_hardening_report.md
2. selected_feature_contracts_hardened.json
3. stage3x_sac_smoke_plan.yaml
4. stage3x_sac_smoke_plan_validation.md
5. feature_contract_redundancy_report.md
6. observation_digest_report.md
7. no_stage_c_access_report.md
```

The smoke plan should explicitly state:

```text
training_launched: false
stage_c_access: DENIED
broad_gpu_allowed: false
small_sac_smoke_allowed: true
ppo_dqn_changed: false
sac_algorithm_source_changed: false
```

---

## 13. Research references

1. Haarnoja et al., **Soft Actor-Critic Algorithms and Applications**, arXiv 1812.05905.  
   https://arxiv.org/abs/1812.05905

2. Haarnoja et al., **Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor**, ICML/PMLR.  
   https://proceedings.mlr.press/v80/haarnoja18b.html

3. Stable-Baselines3, **SAC documentation**. The documented default constructor includes `learning_rate=0.0003`, `batch_size=256`, `tau=0.005`, `gamma=0.99`, and `ent_coef='auto'`.  
   https://stable-baselines3.readthedocs.io/en/master/modules/sac.html

4. Deb et al., **A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II**, IEEE Transactions on Evolutionary Computation, 2002.  
   https://sci2s.ugr.es/sites/default/files/files/Teaching/OtherPostGraduateCourses/Metaheuristicas/Deb_NSGAII.pdf

5. DEAP documentation, **Evolutionary tools / NSGA-II selection**.  
   https://deap.readthedocs.io/en/master/api/tools.html

6. Agarwal et al., **Deep Reinforcement Learning at the Edge of the Statistical Precipice**, NeurIPS 2021.  
   https://arxiv.org/abs/2108.13264

7. Scikit-learn, **mutual_info_regression** documentation.  
   https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.mutual_info_regression.html

8. Lundberg and Lee, **A Unified Approach to Interpreting Model Predictions**, NeurIPS 2017.  
   https://proceedings.neurips.cc/paper/7062-a-unified-approach-to-interpreting-model-predictions.pdf

9. Binance official docs, **USDⓈ-M Futures Funding Rate History**.  
   https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History

10. Binance official docs, **USDⓈ-M Futures Open Interest**.  
    https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest

11. Deribit official docs, **Volatility Index Data**.  
    https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data

12. ALFRED / St. Louis Fed, **Archival FRED vintage data**.  
    https://alfred.stlouisfed.org/

13. Politis and Romano, **The Stationary Bootstrap**, Journal of the American Statistical Association, 1994.  
    https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf

14. Bailey and López de Prado, **The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality**.  
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

15. Bailey et al., **The Probability of Backtest Overfitting**.  
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

---

## 14. Self-critique of this review

1. **No repository access.** This memo relies only on the attached artifacts and public references. It cannot verify whether `selected_feature_contracts.json` has additional fields not present in the Markdown summary.

2. **SAC ranges are conservative.** The recommended hyperparameter ranges are intentionally narrow around documented SAC defaults and the existing schema. This may miss a profitable extreme configuration, but it is the correct trade-off before the pipeline proves that features, observations, costs, and actions are wired correctly.

3. **CPU proxy quality is uncertain.** Rank IC, mutual information, and regime-conditioned proxy return can reject bad contracts, but they cannot prove RL profitability. They should gate GPU use, not replace Stage B.

4. **The selected contracts are BTC-heavy.** That is acceptable for a first smoke test, but not enough to conclude anything about ETH, broader crypto, FX, or source-family value.

5. **No profit guarantee.** The recommendations are designed to stop wasting GPU and money and to increase the chance of finding a real cost-adjusted edge. They do not imply that SAC will become profitable.

6. **Promotion gates remain separate.** This memo recommends a smoke path, not Stage C promotion. DSR, PBO, family tests, paired seeds, and cost stress remain necessary later.

---

## 15. Final reviewer recommendation

Proceed with Stage 3X, but keep it narrow:

```text
1. Harden the CPU screen with observation/feature hash and additional cheap checks.
2. Emit a locked SAC smoke plan for 5 diverse contracts.
3. Run only after the smoke-plan validator confirms Stage C denial and evidence contracts.
4. Treat every smoke run as a counted trial.
5. Start DEAP/NSGA-II only if smoke proves the contracts are non-degenerate.
6. Keep paid data, synthetic data, PPO/DQN expansion, and broad GPU matrices deferred.
```

The most pragmatic next status is:

```text
STAGE_C_ALLOWED = false
BROAD_GPU_ALLOWED = false
SMALL_SAC_SMOKE_ALLOWED = true
NEXT_ACTION = harden_cpu_screen_then_emit_locked_sac_smoke_plan
```
