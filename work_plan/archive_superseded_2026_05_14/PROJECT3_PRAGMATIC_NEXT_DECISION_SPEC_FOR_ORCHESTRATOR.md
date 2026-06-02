# Project 3 Pragmatic Next-Decision Specification for the Orchestrator

**Document type:** implementation-grade orchestration memo / work-plan integration spec.  
**Audience:** Project 3 orchestrator agent, Tier 1/Tier 2 supervisors, and engineering agents working on `financial-data`, `agent-multi`, `synthetic-datagen`, and related repos.  
**Reviewer stance:** senior quant/RL reviewer with profit-first but evidence-disciplined priorities.  
**Generated for:** current Project 3 Stage B / Phase 3.1 decision point.  
**Core instruction:** do not confuse “strict controls” with “academic posturing.” Controls exist only to prevent wasting compute, protecting the 2025+ heldout, and avoiding false profitable-looking policies that will collapse under costs or live deployment.

---

## 1. Executive decision

The current state should **not** be interpreted as “RL cannot trade” or “Project 3 failed.” It should be interpreted as:

```text
The current Stage B evidence is not yet decision-grade enough to send anything to Stage C,
but it is sufficient to direct the next pragmatic engineering work.
```

The present blockers are not all equal. Some are economic blockers, some are missing-artifact blockers, and some are statistical-evidence blockers.

The pragmatic decision is:

```text
STAGE_C_ALLOWED = false
DO_NOT_PROMOTE_CURRENT_CANDIDATES = true
CONTINUE_STAGE_B_REPAIR_AND_TARGETED_FEATURE/SOURCE ITERATION = true
DO_NOT_STOP PROJECT 3 = true
```

The current report says:

```text
Evidence files validated: 50
Evidence failures: 0
DSR pass/fail using N_raw: 0 / 50
Candidate gates pass/fail: 0 / 22
Stage C allowed: false
Main blockers:
  DSR_RIGOROUS_FAIL
  FAMILY_REALITY_CHECK_FAIL
  PBO_DEFERRED_OR_FAIL
  SEED_UNCERTAINTY_BLOCKED
  FINAL_ALWAYS_IN_MARKET_LOSING
  FINAL_EXCESSIVE_TRADES_HARD
  MISSING_COST_SCENARIO
```

That does **not** mean the project should stop. It means the current candidates should not be promoted to the 2025+ heldout. There is a big difference.

The next practical goal is not to prove a theorem. The next practical goal is:

```text
Find whether any asset / timeframe / feature / source combination produces net positive,
non-degenerate, cost-resilient, seed-stable validation behavior before touching Stage C.
```

---

## 2. What is actually blocking progress?

### 2.1 The most immediate blockers are economic and operational, not abstract statistical formalism

The current blockers should be triaged as follows.

| Blocker | Type | What it means pragmatically | Should it block research continuation? | Should it block Stage C? |
|---|---|---|---:|---:|
| `MISSING_COST_SCENARIO` | operational/economic | The run cannot be judged as a trading strategy because realistic net performance is incomplete. | No, fix and rerun. | Yes. |
| `FINAL_ALWAYS_IN_MARKET_LOSING` | economic/behavioral | The policy may have learned static exposure or bad reward dynamics, not trading. | No, use as diagnosis. | Yes. |
| `FINAL_EXCESSIVE_TRADES_HARD` | economic/execution | The policy may be overtrading and giving away edge to costs. | No, use as diagnosis. | Yes. |
| `SEED_UNCERTAINTY_BLOCKED` | empirical RL reliability | One lucky seed cannot be trusted. | No, rerun paired seeds. | Yes. |
| `PBO_DEFERRED_OR_FAIL` | selection stability | Ranking may not be stable across time folds. | No, improve PBO and continue. | Yes for promotion. |
| `FAMILY_REALITY_CHECK_FAIL` | family-level data-snooping | The feature/source family has not beaten baseline after search correction. | No, use to guide family redesign. | Yes for family claim / Stage C. |
| `DSR_RIGOROUS_FAIL` | multiple-testing/statistical | The observed Sharpe is not strong enough after broad search correction. | No, if used as exploration signal. | Yes for promotion. |

### 2.2 The key clarification

A failed DSR or Reality Check **must not** be used to stop all exploration. It should only block claims like:

```text
“This candidate is reliable enough for Stage C.”
```

It should **not** block claims like:

```text
“This failure gives us information about what to test next.”
```

The orchestrator should distinguish:

```text
A. Research continuation gates
B. Stage B promotion gates
C. Stage C launch gates
```

The current state fails **B** and **C**, not necessarily **A**.

---

## 3. Pragmatic gate hierarchy

### 3.1 Gate class A — hard stop for all work

These are catastrophic and must stop affected work immediately:

```text
1. Any Stage C / 2025-01-01+ contamination before final locked heldout.
2. Any validation or Stage C rows inside training, fitting, scaling, feature selection, synthetic generation, prompt context, or threshold selection.
3. Any artifact that cannot be mapped to run_id, config_hash, git_commit, split_manifest, and data windows.
4. Any evaluator bug that computes net metrics from gross returns or ignores costs.
```

These are not academic. They protect the only out-of-sample evidence the project has.

### 3.2 Gate class B — hard stop for Stage C, not for research

These block Stage C but should feed the next iteration:

```text
1. DSR_RIGOROUS_FAIL
2. FAMILY_REALITY_CHECK_FAIL
3. PBO_DEFERRED_OR_FAIL
4. SEED_UNCERTAINTY_BLOCKED
5. MISSING_COST_SCENARIO
6. FINAL_ALWAYS_IN_MARKET_LOSING
7. FINAL_EXCESSIVE_TRADES_HARD
```

Action:

```text
Do not promote.
Do not stop Project 3.
Generate root-cause diagnostics and run targeted next experiments.
```

### 3.3 Gate class C — warnings that should guide iteration

These should not kill a research branch alone:

```text
1. DSR_N_eff passes but DSR_N_raw fails.
2. PBO-lite fails but full purged retraining CSCV has not yet been attempted.
3. White Reality Check fails but SPA is borderline.
4. A feature family is weak globally but strong in one train-only regime.
5. A representation family is unstable but reduces drawdown in some seeds.
```

Action:

```text
Keep exploratory.
Do not promote.
Use the information for feature/source redesign.
```

---

## 4. Profit-oriented interpretation of the current metrics

### 4.1 `DSR_RIGOROUS_FAIL`

The Deflated Sharpe Ratio is not a profit metric. It is a false-discovery filter. It asks:

```text
After all the variants we tried, is the observed Sharpe likely to be more than a lucky winner?
```

For broad searches, `N_raw` is harsh by design. That harshness is appropriate for Stage C promotion, but it can be too harsh as a signal-discovery development metric.

**Pragmatic policy:**

```text
Use DSR_N_raw to block Stage C.
Use raw net return, cost-adjusted Sharpe, drawdown, trade behavior, and paired seed deltas to guide next research.
Do not use DSR_N_raw to stop all feature/asset exploration.
```

The DSR paper’s purpose is correcting Sharpe inflation from multiple testing and non-normal returns, not telling a research program to stop testing new hypotheses.  
Primary source: Bailey and López de Prado, “The Deflated Sharpe Ratio”: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf

### 4.2 `FAMILY_REALITY_CHECK_FAIL`

A family-level Reality Check or SPA failure says:

```text
Within this family of alternatives, the observed winner is not clearly better than baseline
after accounting for data snooping.
```

This is useful because Project 3 tests many feature families. But again, it does not mean the asset or RL approach is impossible. It means the current feature/source family did not yet prove marginal value.

**Pragmatic policy:**

```text
Use RC/SPA to decide whether a family is promotion-grade.
Use family-level failure to prioritize ablation and redesign.
Do not use it as a global project-kill signal.
```

Primary sources:  
White, “A Reality Check for Data Snooping”: https://www.ssc.wisc.edu/~bhansen/718/White2000.pdf  
Hansen, “A Test for Superior Predictive Ability”: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569

### 4.3 `PBO_DEFERRED_OR_FAIL`

PBO asks whether the in-sample winner degrades out-of-sample across folds. For financial time series, random k-fold is invalid; folds must be contiguous, purged, and embargoed where needed.

**Pragmatic policy:**

```text
If PBO-lite fails, do not send to Stage C.
If PBO-lite is deferred, do not pretend Stage B is decision-grade.
But do continue targeted Stage B experiments.
```

Primary source: Bailey et al., “The Probability of Backtest Overfitting”: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

### 4.4 `SEED_UNCERTAINTY_BLOCKED`

This is one of the most practically important blockers. Deep RL can produce high-variance results across seeds. One lucky seed is not a deployable strategy.

**Pragmatic policy:**

```text
Stage B promotion requires at least 5 paired seeds.
10 paired seeds are preferred for serious promotion discussion.
Research smoke tests can use fewer seeds, but they must not promote.
```

Primary source: Agarwal et al., “Deep Reinforcement Learning at the Edge of the Statistical Precipice”: https://arxiv.org/abs/2108.13264  
RL evaluation tooling: https://github.com/google-research/rliable

### 4.5 `FINAL_ALWAYS_IN_MARKET_LOSING`

This is an economic failure, not a statistical nuance. If a policy is nearly always exposed and loses money, it is likely not making adaptive trading decisions.

Possible causes:

```text
1. Reward function rewards exposure or fails to punish bad exposure.
2. Action mapping creates persistent position bias.
3. Environment does not make flat/hold attractive enough after costs.
4. Policy collapsed into buy-and-hold-like behavior.
5. Feature inputs do not expose relevant state for exits.
6. Cost model is too weak during training and stronger during evaluation.
```

Required diagnostic:

```text
Compare against always-flat, always-long, always-short, buy-and-hold, and turnover-matched random baselines.
If the agent loses while always in market, do not promote.
```

### 4.6 `FINAL_EXCESSIVE_TRADES_HARD`

This is also economic. If the policy trades too much, apparent gross edge can be destroyed by costs.

Required diagnostics:

```text
1. trades_per_bar
2. turnover_per_bar
3. cost_to_gross_edge_ratio
4. average_holding_period
5. slippage sensitivity
6. net performance under +50% and +100% cost scenarios
```

Hard fail for Stage C:

```text
if net edge collapses under base cost or modest pessimistic cost:
    no Stage C
```

### 4.7 `MISSING_COST_SCENARIO`

This is the most obviously pragmatic blocker.

If cost scenarios are missing, the project does not know whether the strategy makes money. This is not formalism. It is basic financial management.

Minimum required scenarios:

```text
base
base + 50% fees/slippage
base + 100% fees/slippage
```

---

## 5. Required immediate root-cause report: `stageb_no_pass_root_cause.md`

The orchestrator should produce a short but explicit report before launching more broad jobs.

### 5.1 Required questions

```text
1. Are candidates failing because they lose money net of costs?
2. Are candidates failing because they overtrade?
3. Are candidates failing because they are always exposed and losing?
4. Are candidates failing because cost scenarios are missing?
5. Are candidates failing because seed count is insufficient?
6. Are candidates failing because DSR_N_raw is too conservative for exploration?
7. Are candidates failing because family manifests / matched baselines are incomplete?
8. Are candidates failing because PBO-lite is not enough or because ranking truly degrades?
9. Are candidates failing because tech_stat is too broad/noisy?
10. Are candidates failing because the current asset/timeframe feature stack is weak?
```

### 5.2 Required classification

Each blocker should be classified as:

```text
infrastructure_missing
metric_computation_issue
insufficient_repetitions
statistical_non_significance
economic_failure
trade_behavior_failure
feature_family_failure
source_family_failure
cost_model_failure
```

This is the practical way to avoid arguing about formalism. It tells the team whether to fix code, run more seeds, fix costs, change features, or abandon a branch.

---

## 6. Stage B evaluator pragmatic spec

### 6.1 What must remain strict

The evaluator must stay fail-closed for Stage C promotion:

```text
promotion_allowed = false
```

if any of these are true:

```text
1. Stage C contamination.
2. Missing cost scenario.
3. Missing return trace.
4. Missing ledger entry.
5. Missing matched baseline.
6. Fewer than 5 paired seeds.
7. Synthetic validation rows or synthetic-only evidence used for promotion.
8. Net performance only available before costs.
9. Always-in-market losing final behavior.
10. Excessive-trading hard failure under base or pessimistic costs.
```

### 6.2 What should not block research continuation

The following should block promotion, but should **not** stop targeted next work:

```text
1. DSR_N_raw fail.
2. Reality Check / SPA fail.
3. PBO-lite fail.
4. DSR_N_eff pass but DSR_N_raw fail.
5. Single feature family underperformance.
6. One asset/timeframe family failure.
```

The orchestrator must therefore emit two decisions:

```json
{
  "stage_c_promotion_allowed": false,
  "research_continuation_allowed": true,
  "next_action_class": "diagnose_and_iterate"
}
```

### 6.3 Recommended evaluator output fields

```text
candidate_id
run_id
asset
timeframe
algorithm
feature_preset
feature_family
source_family
seed_set
cost_scenarios_present
cost_scenarios_missing
n_paired_seeds
net_return_median
net_return_iqm
sharpe_median
max_drawdown_median
turnover_median
cost_to_gross_edge_ratio
trades_per_bar
fraction_time_in_market
always_in_market_losing_flag
excessive_trade_flag
no_trade_flag
DSR_N_raw
DSR_N_eff
PBO_lite
White_RC_pvalue
SPA_pvalue
stage_c_promotion_allowed
research_continuation_allowed
blocking_reasons
recommended_next_action
```

---

## 7. Profit-pragmatic next experiment design

### 7.1 Do not launch a huge new matrix blindly

The old project philosophy is comprehensive, but after the current Stage B results, the next step should be **targeted**, not exhaustive.

Do **not** immediately launch thousands more runs. Instead:

```text
1. Fix missing economic evidence.
2. Diagnose trade behavior.
3. Reduce feature noise.
4. Add the most plausible low-cost features.
5. Run paired seeds on a small set of high-information variants.
```

### 7.2 First target remains ETHUSDT 4h SAC

Even if the current candidate is blocked, it remains useful as the first controlled diagnostic target:

```text
asset: ETHUSDT
timeframe: 4h
algorithm: SAC
base feature family: tech_stat
```

Reason:

```text
It is the closest thing to a live signal family so far.
It is slow enough to be less microstructure-dominated than 15m.
It is liquid enough to evaluate costs.
It is already instrumented in Stage B.
```

### 7.3 First paired Stage B diagnostic matrix

Run the following **small** paired matrix:

```text
A. baseline_12
B. tech_stat_full
C. tech_stat_reduced_corr_v1
D. tech_stat_volatility_only
E. tech_stat_trend_only
F. tech_stat_momentum_only
G. tech_stat_volume_liquidity_only
H. tech_stat_full + train_only_regime_probs
I. tech_stat_reduced_corr_v1 + train_only_regime_probs
J. tech_stat_full + train_only_ood_score
```

Required:

```text
algorithm: SAC only for first diagnostic pass
seeds: [0, 1, 2, 3, 4] minimum
costs: base, +50%, +100%
validation: real validation only
Stage C: untouched
```

Only after this, consider PPO/DQN or additional assets.

### 7.4 Why this matrix is pragmatic

This matrix answers practical questions:

```text
1. Is tech_stat better than baseline_12?
2. Is tech_stat too noisy/high-dimensional?
3. Which subfamily drives behavior: trend, momentum, volatility, volume?
4. Do regime features reduce always-in-market losing behavior?
5. Do OOD features reduce excessive trading or bad drawdowns?
6. Does any variant survive realistic costs?
```

This is more useful than launching another broad search without understanding why the current candidate failed.

---

## 8. Feature/source implementation plan

### 8.1 Current feature base is large enough to require selection, not just expansion

Project 3 already has:

```text
technical/statistical features
cross-source statistical features
signal decomposition features
learned LSTM/CNN autoencoder embeddings
multi-asset/multi-timeframe data
```

The risk is now feature noise, redundancy, and overfit.

### 8.2 Immediate feature tasks

#### Task F1 — feature registry

Create:

```text
features/FEATURE_REGISTRY.parquet
features/FEATURE_FAMILY_REGISTRY.yaml
features/SOURCE_FAMILY_REGISTRY.yaml
features/FEATURE_AVAILABILITY_AUDIT.md
```

Required fields:

```text
feature_name
feature_family
source_family
asset
timeframe
input_files
fit_start
fit_end
availability_timestamp_rule
max_lookback_bars
uses_fitted_transform
fit_uses_validation
fit_uses_stage_c
missingness_rate
warmup_bars
config_hash
git_commit
```

#### Task F2 — split `tech_stat` into subfamilies

```text
return
trend
momentum
volatility
volume_liquidity
rolling_moments
dependence
regime_flags
```

This is required because `tech_stat` is currently too broad. A full `tech_stat` result does not tell the project what created the behavior.

#### Task F3 — redundancy reduction

Implement:

```text
near_zero_variance_filter
missingness_filter
spearman_correlation_clusterer
family_aware_representative_selector
```

Output:

```text
tech_stat_reduced_corr_v1.parquet
tech_stat_reduced_corr_v1.yaml
feature_redundancy_report.md
```

Acceptance:

```text
All fitting uses train only.
No validation PnL is used to select features.
The selected feature set is counted as a new feature-family variant.
```

#### Task F4 — regime and OOD features

Add:

```text
train_only_hmm_regime_probs
train_only_gmm_regime_probs
regime_entropy
regime_transition_probability
robust_mahalanobis_ood
knn_latent_ood
```

Acceptance:

```text
No validation fitting.
No Stage C fitting.
HMM features use filtered probabilities p(z_t | x_<=t), not full-sequence smoothing.
Thresholds, if any, are train-calibrated only.
```

Primary references:  
Hamilton, Markov-switching regimes: https://www.jstor.org/stable/1912559  
Tigramite/PCMCI+ later if causal discovery is needed: https://jakobrunge.github.io/tigramite/

---

## 9. Source-family next tasks

### 9.1 Crypto spot

Keep first decision-grade tests focused on:

```text
BTCUSDT
ETHUSDT
```

Add only after controlled evidence:

```text
SOLUSDT
BNBUSDT
LINKUSDT
DOGEUSDT
```

Feature additions:

```text
BTC/ETH beta
cross-asset correlation
relative strength
realized volatility of volatility
jump-robust realized moments
```

Primary reference for jump-robust realized volatility:  
Barndorff-Nielsen and Shephard, bipower variation: https://public.econ.duke.edu/~get/browse/courses/883/Spr16/COURSE-MATERIALS/Z_Papers/BNSJFEC2004.pdf

### 9.2 Crypto perps

Add as a separate source family, not mixed silently into `tech_stat`:

```text
funding_rate
funding_zscore
funding_term_structure
open_interest
open_interest_change
basis_or_premium_index
mark_vs_index_divergence
```

Primary sources:  
Binance funding-rate history: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History  
Binance open interest: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest

### 9.3 FX

Focus on:

```text
EURUSD
USDJPY
```

Add feature families:

```text
carry / policy-rate differential
FX momentum
FX value proxy
session-aware volatility
global FX volatility
COT positioning, if available and timestamp-safe
```

Primary source for FX carry factor literature:  
Lustig, Roussanov, Verdelhan, common risk factors in currency markets: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1139447

### 9.4 Macro and volatility risk

Add only with point-in-time semantics:

```text
yield curve slope
rate differential
VIX / macro risk proxy
variance risk premium
crypto DVOL / crypto VRP
```

Primary sources:  
ALFRED vintage macro data: https://alfred.stlouisfed.org/  
Deribit volatility-index endpoint: https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data  
Bollerslev/Tauchen/Zhou variance risk premia: https://academic.oup.com/rfs/article/22/11/4463/1567695

---

## 10. Representation-learning plan

### 10.1 Do not add every representation at once

The current learned LSTM/CNN embeddings already exist. Do not immediately add PCA, VAE, TS2Vec, PatchTST, CoST, Chronos, and MOMENT all together. That creates a new uncontrolled search surface.

### 10.2 Recommended order

```text
P0:
  Evaluate existing learned_lstm and learned_cnn against tech_stat and baseline_12.
  Verify encoders were fit train-only for each Stage B split.

P1:
  Add PCA compression as a transparent baseline.
  Add TS2Vec_v1 as the first contrastive representation.

P2:
  Add PatchTST_SSL or CoST only after TS2Vec has a clean paired comparison.
  Add TimeVAE/CVAE only after simpler representations are evaluated.
  Use time-series foundation models only as diagnostics or frozen embeddings, not direct signals.
```

Primary sources:  
TS2Vec: https://arxiv.org/abs/2106.10466  
PatchTST: https://arxiv.org/abs/2211.14730  
CoST: https://arxiv.org/abs/2202.01575  
TimeVAE: https://arxiv.org/abs/2111.08095

---

## 11. Synthetic data Phase 4 policy

### 11.1 Synthetic data is not the answer to weak real evidence

Synthetic data can help training robustness. It cannot prove tradability.

Allowed:

```text
pretraining
augmentation
stress testing
rare-regime exposure
policy robustness diagnostics
```

Forbidden:

```text
synthetic validation evidence
synthetic heldout replacement
training generator on 2025+ data
tuning generator on validation PnL
directly generating deterministic indicator columns
using synthetic-only performance as promotion evidence
```

### 11.2 Keep Phase 4 deferred until Stage B real-data packet exists

Phase 4 should stay optional/deferred until:

```text
1. real-data-only candidate configurations are identified;
2. simple baselines exist;
3. feature/source ablations exist;
4. leakage and heldout audits pass;
5. Stage C remains untouched;
6. the synthetic generator passes memorization gates.
```

### 11.3 Preferred generator order

```text
P0:
  moving-block bootstrap
  stationary bootstrap
  non-overlapping block bootstrap
  regime residual bootstrap

P1:
  GARCH/HMM residual generator
  TimeVAE/CVAE

P2:
  TimeGAN
  COT-GAN
  Sig-Wasserstein GAN
  diffusion / FTS-Diffusion
```

Primary sources:  
Stationary bootstrap: https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf  
TimeGAN: https://papers.neurips.cc/paper/8789-time-series-generative-adversarial-networks  
COT-GAN: https://arxiv.org/abs/2006.08571  
TimeVAE: https://arxiv.org/abs/2111.08095  
FTS-Diffusion: https://proceedings.iclr.cc/paper_files/paper/2024/file/f90fc76b199fe6b0ec2a51aaf72c3277-Paper-Conference.pdf

### 11.4 Synthetic trial counting

Every synthetic-augmented run is a tested training-protocol variant:

```text
training_protocol_family = synthetic_pretrain_then_real_finetune
synthetic_generator_family = regime_residual_bootstrap_v1
synthetic_ablation_id = <ratio/schedule/hash>
```

Count in the multiple-testing ledger:

```text
generator_family_id
generator_config_hash
anti_mem_evaluator_version
augmentation_ratio
pretraining_schedule
real_finetune_schedule
seed set
cost scenario
asset/timeframe/algorithm/feature_preset
```

---

## 12. P0 implementation work packet for the orchestrator

### 12.1 P0.1 — complete Stage B evidence integrity

**Objective:** make every Stage B blocker actionable and reproducible.

Tasks:

```text
[ ] Verify all Stage B traces are synced from Dragon/Gamma/Omega.
[ ] Run stage_b_cluster_live_status_worker.py.
[ ] Run stage_b_run_plan_status_worker.py.
[ ] Run stageb_dsr_pbo_evaluator.py.
[ ] Run stage_b_approval_gate_worker.py.
[ ] Generate stage_b_summary.md only after evaluator and gate refresh.
```

Acceptance:

```text
[ ] Every candidate has run_id, config_hash, git_commit, trace path, evidence sidecar.
[ ] Every blocker maps to a concrete artifact and reason.
[ ] Stage C remains false unless all hard gates pass.
```

### 12.2 P0.2 — resolve missing cost scenarios

Tasks:

```text
[ ] Define required cost_scenarios = [base, plus_50pct, plus_100pct].
[ ] For every candidate/cost scenario, verify net returns exist.
[ ] If missing, rerun evaluation or mark MISSING_COST_SCENARIO as hard fail.
[ ] Emit cost_scenario_manifest.yaml.
```

Acceptance:

```text
[ ] No candidate is promotion-eligible without base and pessimistic costs.
[ ] Cost-to-gross-edge ratio is computed.
[ ] Net metrics always refer to after-cost returns.
```

### 12.3 P0.3 — trade behavior report

Tasks:

```text
[ ] Compute no_trade_flag.
[ ] Compute always_in_market_losing_flag.
[ ] Compute excessive_trade_flag.
[ ] Compute trades_per_bar.
[ ] Compute turnover_per_bar.
[ ] Compute average_holding_period.
[ ] Compute fraction_time_in_market.
[ ] Compute cost_to_gross_edge_ratio.
[ ] Generate trade_behavior_report.csv.
[ ] Generate trade_behavior_report.md.
```

Acceptance:

```text
[ ] FINAL_ALWAYS_IN_MARKET_LOSING is explainable by metrics.
[ ] FINAL_EXCESSIVE_TRADES_HARD is explainable by metrics.
[ ] No-trade, always-in-market, and excessive-trade states produce explicit reasons.
```

### 12.4 P0.4 — `stageb_no_pass_root_cause.md`

Tasks:

```text
[ ] Group failures by infrastructure, statistical, economic, and behavior causes.
[ ] Explain why 0/22 gates passed.
[ ] Identify whether DSR_N_raw is blocking all candidates despite positive net behavior.
[ ] Identify candidates that fail economically before statistics.
[ ] Identify candidates that are worth rerunning with more seeds.
[ ] Identify feature/source families that should be killed or redesigned.
```

Acceptance:

```text
[ ] The report tells the orchestrator what to do next.
[ ] The report does not simply say “no candidates passed.”
```

### 12.5 P0.5 — first paired ETHUSDT 4h SAC diagnostic run

Manifest:

```yaml
experiment_id: stageb_ethusdt_4h_sac_pragmatic_diagnostic_v1
asset: ethusdt
timeframe: 4h
algorithm: SAC
stage_c_allowed: false
seeds: [0, 1, 2, 3, 4]
cost_scenarios: [base, plus_50pct, plus_100pct]
feature_variants:
  - baseline_12
  - tech_stat_full
  - tech_stat_reduced_corr_v1
  - tech_stat_volatility_only
  - tech_stat_trend_only
  - tech_stat_momentum_only
  - tech_stat_volume_liquidity_only
  - tech_stat_full_plus_regime_probs
  - tech_stat_reduced_corr_v1_plus_regime_probs
  - tech_stat_full_plus_ood_score
```

Acceptance:

```text
[ ] All variants use identical SAC configuration.
[ ] All variants use identical train/validation split.
[ ] All variants use identical costs.
[ ] All variants produce return traces and trade behavior reports.
[ ] Stage C is not touched.
```

---

## 13. P1 implementation work packet

### 13.1 Feature/source additions with best expected practical value

Implement in this order:

```text
1. tech_stat_reduced_corr_v1
2. train_only_hmm/gmm_regime_probs
3. jump_robust_realized_moments_v1
4. crypto_funding_open_interest_v1
5. BTC/ETH cross-asset beta/correlation features
6. FX carry proxies for EURUSD and USDJPY
7. DVOL/crypto_VRP if provenance is stable
8. TS2Vec_v1 representation
```

### 13.2 Acceptance rules

For each new family:

```text
[ ] Train-only fitting.
[ ] No Stage C data.
[ ] Feature registry entry.
[ ] Source family entry.
[ ] Matched baseline comparison.
[ ] Counted in N_raw / family tests.
[ ] Real validation only.
```

---

## 14. P2 items to defer

Do not spend immediate compute here unless P0/P1 produce a positive real-validation signal:

```text
TimeGAN
COT-GAN
Sig-Wasserstein GAN
Diffusion / FTS-Diffusion
foundation time-series model embeddings
TradingAgents / LLM committee overlay
PCMCI+ causal feature selection
regime-specific policies
new RL algorithms
```

Reason:

```text
These are not useless. They are too many degrees of freedom before the current economic and Stage B blockers are resolved.
```

---

## 15. Required final outputs for this work packet

The orchestrator should produce:

```text
experiments/stage_b_validation/stage_b_summary.md
experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md
experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json
experiments/stage_b_validation/hardening/trade_behavior_report.csv
experiments/stage_b_validation/hardening/trade_behavior_report.md
experiments/stage_b_validation/hardening/cost_fragility_report.csv
experiments/stage_b_validation/hardening/cost_fragility_report.md
experiments/stage_b_validation/hardening/stageb_no_pass_root_cause.md
experiments/stage_b_validation/hardening/promotion_decision.json
features/FEATURE_REGISTRY.parquet
features/FEATURE_FAMILY_REGISTRY.yaml
features/SOURCE_FAMILY_REGISTRY.yaml
features/FEATURE_AVAILABILITY_AUDIT.md
experiments/stage_b_validation/manifests/stageb_ethusdt_4h_sac_pragmatic_diagnostic_v1.yaml
```

---

## 16. What would violate Stage C and must not be done

Hard forbidden:

```text
1. Use rows at or after 2025-01-01 for any training, fitting, scaling, synthetic generation, feature selection, threshold selection, prompt context, or report calibration.
2. Run Stage C because “we need to see what happens.”
3. Run Stage C more than once.
4. Change feature selection after seeing Stage C.
5. Change cost model after seeing Stage C.
6. Use synthetic data to create heldout-like evidence.
7. Use validation-tuned synthetic generators and report only the best.
8. Drop failed candidates from N_raw or family tests.
9. Promote seed 0 alone.
10. Change PPO/SAC/DQN configs while claiming fixed-algorithm comparison.
```

---

## 17. Critique of the current requirements

### 17.1 Good requirements

The following are not academic posturing; they are economically necessary:

```text
1. Net returns after realistic costs.
2. Trade behavior gates.
3. Paired seed checks.
4. Stage C firewall.
5. Matched baselines.
6. Feature/source ablations.
7. Synthetic-data quarantine.
```

These directly protect capital and compute.

### 17.2 Requirements that can become counterproductive if misused

#### DSR_N_raw as an exploration stopper

`DSR_N_raw` is appropriate for promotion, but can be too punitive for exploration after a broad Stage A. Do not use `DSR_N_raw` to declare that no further feature or asset work is worthwhile.

Correct use:

```text
Blocks Stage C.
Does not block research continuation.
```

#### Family Reality Check as a universal kill switch

A family Reality Check failure says the current family has not proven superiority. It does not mean all variants of that family are useless forever.

Correct use:

```text
Blocks family-level claims.
Guides redesign or ablation.
```

#### PBO-lite as if it were full CSCV

PBO-lite over validation traces is useful, but it is not the same as full retrained purged CSCV.

Correct use:

```text
Use PBO-lite as a screening diagnostic.
Use full purged CSCV for true finalists if compute permits.
```

### 17.3 Missing pragmatic requirement

The current governance should add a specific root-cause report:

```text
stageb_no_pass_root_cause.md
```

Without that report, the team may incorrectly interpret `0/22 gates pass` as “the project failed,” instead of identifying whether the issue is costs, trade behavior, seed count, feature noise, source weakness, or actual absence of edge.

---

## 18. Critique of this memo

This memo is intentionally conservative about Stage C. That is appropriate because Stage C is the only clean heldout. However, this memo may still underweight the business urgency of finding profitable candidates quickly.

The correction is:

```text
Do not loosen Stage C.
Do speed up Stage B iteration.
```

That means:

```text
1. Use small high-information experiment matrices.
2. Focus on economic blockers first.
3. Reduce feature noise before adding deep methods.
4. Add only the highest-probability source families.
5. Use fast paired seed tests before broad search.
```

The memo also assumes that the current cost model is directionally valid. If the cost model is wrong, all conclusions about excessive trading and profitability can be wrong. Therefore, cost-model review is a P0 dependency.

Finally, the memo does not claim that PPO/SAC/DQN will become profitable. It claims that the current evidence is not enough to reject the project, and that the next pragmatic path is diagnostic, targeted, and cost-aware.

---

## 19. Final orchestrator command summary

```text
1. Keep Stage C locked.
2. Do not promote any current candidate.
3. Produce stageb_no_pass_root_cause.md.
4. Resolve missing cost scenarios.
5. Add/refresh trade_behavior_report.md.
6. Build feature/source registries.
7. Split tech_stat into subfamilies.
8. Build tech_stat_reduced_corr_v1.
9. Build train-only regime/OOD features.
10. Launch small paired ETHUSDT 4h SAC diagnostic matrix.
11. Use results to decide whether to expand to BTCUSDT, perps, FX, or new feature families.
12. Keep synthetic Phase 4 training-only and deferred until real-data evidence exists.
```

---

## 20. GitHub issue checklist

```text
Title:
  Project 3 Pragmatic Stage B Repair and Next Diagnostic Experiment

Priority:
  Critical

Context:
  Current Stage B has 50 validated evidence files, 0 evidence failures,
  but 0/22 candidate gates pass and Stage C allowed=false.

P0 — Do not advance Stage C
  [ ] Confirm Stage C remains locked.
  [ ] Confirm no file/row/prompt/context at or after 2025-01-01 was used.
  [ ] Confirm no current candidate has PASS_STAGE_B_READY.

P0 — Cost and trade behavior
  [ ] Resolve MISSING_COST_SCENARIO for every candidate.
  [ ] Generate cost_scenario_manifest.yaml.
  [ ] Generate trade_behavior_report.csv.
  [ ] Generate trade_behavior_report.md.
  [ ] Add no_trade_flag.
  [ ] Add always_in_market_losing_flag.
  [ ] Add excessive_trade_flag.
  [ ] Add cost_to_gross_edge_ratio.
  [ ] Add fraction_time_in_market.
  [ ] Add average_holding_period.

P0 — Root cause analysis
  [ ] Generate stageb_no_pass_root_cause.md.
  [ ] Classify failures as infrastructure/statistical/economic/behavior/feature/source/cost.
  [ ] Identify candidates worth rerunning with paired seeds.
  [ ] Identify feature families that need reduction or redesign.

P0 — Feature governance
  [ ] Create FEATURE_REGISTRY.parquet.
  [ ] Create FEATURE_FAMILY_REGISTRY.yaml.
  [ ] Create SOURCE_FAMILY_REGISTRY.yaml.
  [ ] Create FEATURE_AVAILABILITY_AUDIT.md.
  [ ] Record max_lookback_bars for every feature preset.
  [ ] Split tech_stat into subfamilies.
  [ ] Build tech_stat_reduced_corr_v1.

P0 — First paired diagnostic matrix
  [ ] Register stageb_ethusdt_4h_sac_pragmatic_diagnostic_v1.yaml.
  [ ] Use fixed SAC config.
  [ ] Use seeds [0,1,2,3,4] minimum.
  [ ] Use cost scenarios [base, plus_50pct, plus_100pct].
  [ ] Run baseline_12.
  [ ] Run tech_stat_full.
  [ ] Run tech_stat_reduced_corr_v1.
  [ ] Run volatility/trend/momentum/volume subfamilies.
  [ ] Run tech_stat + train-only regime probabilities.
  [ ] Run tech_stat + train-only OOD score.
  [ ] Emit return traces and trade behavior reports for all arms.

P1 — High-probability feature/source additions
  [ ] Add train-only HMM/GMM regime features.
  [ ] Add jump-robust realized moments.
  [ ] Add crypto funding/OI features as separate source family.
  [ ] Add BTC/ETH cross-asset beta/correlation.
  [ ] Add FX carry proxies.
  [ ] Add DVOL/crypto VRP only if provenance is stable.
  [ ] Add TS2Vec_v1 only after existing learned embeddings are evaluated.

P2 — Deferred
  [ ] Do not launch TimeGAN/COT-GAN/diffusion yet.
  [ ] Do not launch TradingAgents overlay yet.
  [ ] Do not launch causal feature selection yet.
  [ ] Do not change PPO/SAC/DQN algorithms.

Hard forbidden
  [ ] No Stage C tuning.
  [ ] No Stage C repeated evaluation.
  [ ] No synthetic validation evidence.
  [ ] No validation-tuned feature mask reported as train-only.
  [ ] No dropping failed alternatives from N_raw or family tests.
  [ ] No single-seed promotion.
```

---

## 21. Bottom line

The practical problem is not that Project 3 lacks methodology. The practical problem is that the current Stage B evidence does not yet show a deployable, cost-resilient, seed-stable trading policy.

That is not surprising at this stage. The project has not yet fully exploited targeted feature/asset/source selection, feature extraction, regime/OOD features, source-family ablations, or controlled synthetic pretraining.

The correct business-minded response is:

```text
Do not pretend weak evidence is profit.
Do not waste the heldout.
Do not stop research prematurely.
Fix economic blockers, reduce feature noise, run small paired diagnostics,
and only then decide whether to broaden the search or kill a family.
```

Current status:

```text
STAGE_C_ALLOWED = false
PROMOTION = false
NEXT_ACTION = pragmatic Stage B repair + targeted ETHUSDT 4h SAC diagnostic matrix
```
