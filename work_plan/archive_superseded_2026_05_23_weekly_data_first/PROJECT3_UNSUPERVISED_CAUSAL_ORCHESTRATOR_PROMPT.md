# Orchestrator Prompt — Add Unsupervised Learning + Causal Audit Lane to Project 3 Work Plan

## Codex Review Addendum - 2026-05-03

This ChatGPT 5.5 Pro proposal is accepted as a useful research-engineering direction, but with these corrections before any implementation:

1. **Treat this as `Phase 3X`, not as a new mandatory Stage B blocker.** The lane is additive and may produce registered paired variants for top candidates. It must not pause the current Stage 3.1 matrix or redefine the existing best run.
2. **Start with audit/tooling plus one narrow target.** First target is `ETHUSDT 4h + SAC + tech_stat`; do not fan out across all assets/timeframes until the split guard, metadata contract, and paired-variant registry work.
3. **Every fitted object is train-only.** HMM/GMM/K-means, OOD scalers, feature clusters, causal graphs, SSL encoders, thresholds, and masks must fit only on the declared training split. Validation may only call `transform`, `score`, or `predict_proba`.
4. **Do not use causal discovery as an alpha oracle.** Causal and invariant methods are audit/hypothesis layers. Any feature mask or new feature set must become a pre-registered RL variant and count toward multiple-testing correction.
5. **Fail closed on current-bar availability.** If the environment decision at bar `t` cannot know a value before acting, that value must be shifted or excluded. Causal audit targets may use future labels for offline analysis only, never as observations.
6. **Keep compute discipline.** P0-A/P0-B/P0-D are CPU-first unless a dependency requires GPU; P1 SSL embeddings are deferred until core PPO/SAC/DQN evidence is stable.

Operational status: approved for documentation and narrow P0 tooling design; not approved as a broad implementation sweep yet.

## Copy/paste prompt for the Project 3 orchestrator agent

Act as the Tier 2 Project 3 orchestrator and senior research-engineering planner for a financial-data/RL trading pipeline. Your task is to add a controlled, auditable **Unsupervised Learning + Causal Audit Lane** to the existing Project 3 work plan.

This addition must be conservative, additive, leakage-safe, reproducible, and compatible with the current multi-machine agent infrastructure. Do **not** rewrite the core Project 3 experiment. Do **not** replace PPO/SAC/DQN. Do **not** alter the strict Stage C firewall. The goal is to improve agent robustness, regime awareness, feature quality, OOD detection, and feature-leakage auditing, not to create an uncontrolled new alpha-search loop.

---

## 1. Current project context to preserve

Project 3 is data-centric and feature-centric. The core hypothesis is that better data diversity and better feature representations may improve RL trading performance. The fixed RL algorithms under systematic evaluation are PPO, SAC, and DQN. The primary experimental variables are trading asset, simulation timeframe, feature input set, and feature-engineering technique.

Current known strong candidate:

- Trading asset: `ETHUSDT`
- Simulation timeframe: `4h`
- RL algorithm: `SAC`
- Feature family: `tech_stat`
- Status: best current Stage A signal, but not yet a license to alter held-out discipline.

Existing feature foundation:

- Technical/statistical features are complete.
- Signal-decomposition features are complete.
- LSTM and CNN learned-representation features are available for the active Stage A universe.
- Feature columns include many deterministic OHLCV-derived indicators, so any new model must respect causal feature computation and avoid future-window leakage.

Existing governance to preserve:

- Immutable run ledger.
- Paired feature/source tests.
- Simple baselines.
- Leakage audit.
- Deflated Sharpe Ratio.
- PBO/CSCV-style overfit diagnostics where feasible.
- Realistic cost/slippage gates.
- Stage C firewall.
- No post-2025-01-01 data may be used for training, tuning, feature fitting, unsupervised fitting, causal graph fitting, scaler fitting, threshold selection, synthetic generation, validation, or prompt context.
- Stage C is final held-out evaluation only.
- Synthetic data and unsupervised/causal outputs must never touch Stage C before final frozen evaluation.

Infrastructure constraints to preserve:

- Tier 2 dispatches work across machines.
- Heavy GPU jobs must acquire `/tmp/gpu_busy.lock` before running.
- No automated frontier API calls.
- Frontier models remain Tier 4 human-driven only.
- Tier 3 local automated coding remains bounded by existing attempt/scope/time rules.

---

## 2. Required work-plan addition

Add a new controlled lane named one of the following, depending on where it fits best in the existing numbering:

- Preferred: `Phase 3.x — Unsupervised + Causal Audit Lane`
- Alternative if Phase 3 numbering is already frozen: `Phase 4.1 — Unsupervised + Causal Robustness Layer`

Recommended placement:

- After Stage A identifies strong candidate asset/timeframe/model/feature combinations.
- Before Stage B promotion decisions for the small set of promising candidates.
- Do not run this across the full search space initially.
- First target should be `ETHUSDT 4h + SAC + tech_stat`.

Strategic purpose:

1. Add train-only regime-awareness features.
2. Add train-only OOD/anomaly features.
3. Add feature-redundancy and feature-stability reports.
4. Add causal/leakage audit reports.
5. Add invariant-feature candidate masks.
6. Add policy stress-test diagnostics.
7. Evaluate all additions only through paired real-validation RL tests.

Explicit non-goals:

1. Do not claim causal alpha from observational financial data.
2. Do not use causal discovery as proof of tradability.
3. Do not introduce new RL algorithms in this lane.
4. Do not tune prompts, thresholds, regimes, masks, or feature families using held-out data.
5. Do not let generated/synthetic/unsupervised outputs become evaluation evidence.
6. Do not use Stage C for iterative decisions.

---

## 3. Scientific principle

Treat unsupervised and causal methods as **evidence layers**, not autonomous decision-makers.

Allowed uses:

- Regime probabilities as RL observation features.
- Regime entropy as uncertainty/OOD signal.
- OOD/anomaly score as RL observation feature or deterministic exposure-reduction signal.
- Feature redundancy clusters for controlled feature-set compression.
- Causal graphs as audit artifacts and hypothesis generators.
- Invariant feature scores as candidate feature masks.
- Counterfactual perturbations as policy stress tests.
- Evidence-pack fields for later LLM/agent review overlays.

Forbidden uses:

- Directly selecting final strategies after looking at validation or held-out outcomes.
- Removing or adding features without registering a paired experimental variant.
- Training any unsupervised/causal model on validation or Stage C data.
- Treating synthetic or counterfactual evaluation as real performance evidence.
- Allowing the causal graph to make trades directly.
- Allowing the LLM/agent committee to tune feature masks after seeing Stage C.

---

## 4. P0 implementation tasks — immediate, low-risk, high-value

### 4.1 P0-A — Train-only HMM/GMM regime features

Implement train-only regime labeling for top Stage A candidates.

Initial target:

- `ETHUSDT`
- `4h`
- `SAC`
- `tech_stat`

Candidate input variables, all fitted on train only:

- `log_return_1`
- `roll_std_ret_20`
- `roll_std_ret_60`
- `roll_skew_ret_60`
- `roll_kurt_ret_60`
- `realized_var_12`
- `realized_var_48`
- `autocorr_lag1_100`
- `sqret_autocorr_lag1_100`
- `volume_ratio_20`
- `atr_14`
- `natr_14`
- `trend_slope_50`
- `trend_strength_50`

Required models:

- Gaussian HMM baseline.
- Gaussian Mixture Model baseline.
- K-means baseline only as a cheap sanity check.

Required output features:

- `unsup_regime_id`
- `unsup_regime_prob_0`
- `unsup_regime_prob_1`
- `unsup_regime_prob_2`
- `unsup_regime_entropy`
- `unsup_regime_transition_prob`
- `unsup_regime_persistence`

Required validation artifacts:

- Regime count distribution.
- Regime transition matrix.
- Regime-conditioned return/volatility/drawdown summary.
- Chronological regime plot for train and validation.
- Proof that model parameters and scalers were fitted on train only.
- Proof that no data at or after `2025-01-01` was used.

Acceptance criteria:

- No held-out usage.
- No future-window features.
- All outputs are timestamp-aligned and point-in-time safe.
- Regime features can be loaded by existing Phase 3 feature assembly.
- Paired RL tests can compare baseline vs regime-augmented features.

---

### 4.2 P0-B — OOD/anomaly scoring

Implement train-only OOD scores for top Stage A candidates.

Recommended methods:

- Robust Mahalanobis distance in scaled feature space.
- KNN distance in existing learned LSTM/CNN embedding space.
- Autoencoder reconstruction-error score if existing models expose reconstruction error; otherwise defer to P1.
- Regime entropy as a simple uncertainty proxy.

Required output features:

- `ood_mahalanobis_train_space`
- `ood_knn_latent_distance`
- `ood_regime_entropy`
- `ood_feature_missingness_score`
- `ood_liquidity_volume_anomaly`
- `ood_composite_score`

Required deterministic overlay option:

- If OOD score exceeds train-calibrated threshold, reduce position multiplier to `0.5` or `0.0`.
- Thresholds must be calibrated on train only or pre-registered before validation.
- Compare against RL-only and RL-with-OOD-feature variants.

Acceptance criteria:

- Scores are reproducible.
- Thresholds are not tuned on Stage C.
- The OOD overlay is evaluated as a separate registered variant.
- The overlay may reduce or veto exposure, but must not reverse trades or create new trades.

---

### 4.3 P0-C — Causal/leakage audit baseline

Implement a conservative causal/leakage audit baseline. This is an audit/reporting lane, not an automatic feature selector.

Required analyses:

- Lag-only Granger-style baseline for selected features.
- Simple conditional-dependence screening for candidate parent features.
- Suspicious-feature report for potential leakage.
- Timestamp availability audit for any feature with unusually strong predictive relationship.

Targets to audit:

- `future_return_1`
- `future_return_3`
- `future_return_6`
- `future_realized_volatility`
- `future_drawdown_proxy`
- `future_cost_adjusted_reward_proxy`

Rules:

- Candidate parents must be lagged.
- Do not use current-bar information if the environment action would not have access to it at decision time.
- Do not include post-2025 data.
- Do not automatically remove features without a registered paired experiment.

Required output artifacts:

- `causal_audit_report.md`
- `suspicious_features.parquet`
- `candidate_parent_scores.parquet`
- `timestamp_availability_audit.json`
- `feature_mask_candidates.yaml`

Acceptance criteria:

- The audit identifies leakage risk, redundancy risk, and unstable feature relationships.
- Any proposed feature mask is only a candidate until validated by paired RL experiments.

---

### 4.4 P0-D — Feature redundancy and stability report

Implement train-only feature clustering/redundancy analysis.

Required analyses:

- Correlation clustering.
- Rank-correlation clustering.
- Mutual-information-style screening if available and computationally safe.
- Feature-family redundancy summary.
- Regime-conditioned feature stability summary.

Required outputs:

- `feature_clusters.parquet`
- `feature_cluster_representatives.yaml`
- `feature_redundancy_report.md`
- `feature_stability_by_regime.parquet`

Acceptance criteria:

- Reduced feature sets are not automatically promoted.
- Any reduced feature set becomes a registered experimental variant.
- The report improves interpretability of `tech_stat`, decomposition, and learned feature families.

---

### 4.5 P0-E — Evidence-pack extension for agent overlays

Extend Project 3 evidence packs so future LLM/agent overlays can consume unsupervised and causal diagnostics without touching raw held-out data.

Required evidence-pack fields:

- Regime ID and regime probabilities.
- Regime entropy.
- OOD composite score.
- Feature-family stability status.
- Suspicious-feature warnings.
- Candidate parent summary.
- Deterministic risk overlay recommendation.
- Whether the signal is inside or outside training-support conditions.

Rules:

- Evidence packs must be date-scoped and point-in-time safe.
- Evidence packs must not include Stage C data during design/tuning.
- Evidence packs must not include prompt examples derived from held-out outcomes.

---

## 5. P1 implementation tasks — after P0 passes

### 5.1 P1-A — PCMCI+ causal candidate-parent graphs

Implement Tigramite-based PCMCI+ or equivalent time-series causal discovery for top candidates only.

Purpose:

- Identify plausible lagged parent features.
- Detect unstable or suspicious relationships.
- Create candidate feature masks for paired validation.

Rules:

- Train-only fitting.
- Lagged candidate parents only unless contemporaneous availability is explicitly justified.
- Separate graph per asset/timeframe/feature set.
- Stability across chronological folds and regimes must be reported.
- Graph results are hypotheses, not proof.

Required outputs:

- `causal_graph_<asset>_<timeframe>.json`
- `causal_graph_<asset>_<timeframe>.png` or `.svg`
- `causal_parent_scores.parquet`
- `causal_graph_stability_report.md`
- `causal_feature_mask_candidates.yaml`

Acceptance criteria:

- No held-out usage.
- Causal graph is reproducible under fixed seeds/config.
- Feature masks are evaluated only through paired RL validation.

---

### 5.2 P1-B — Invariant feature scoring

Implement invariant feature scoring across environments.

Define environments before fitting. Candidate environment types:

- Chronological train folds.
- Regime buckets.
- Asset families: crypto spot, crypto perp, FX.
- Timeframes: 15m, 1h, 4h where relevant.
- Volatility states: low, medium, high.

Required outputs:

- `invariant_feature_scores.parquet`
- `invariant_feature_mask_candidates.yaml`
- `invariance_report.md`

Required score fields:

- Feature name.
- Target name.
- Environments tested.
- Mean effect sign.
- Sign stability.
- Rank stability.
- Regime stability.
- Recommended action: `keep`, `downweight`, `audit`, or `reject_candidate`.

Rules:

- Do not remove features automatically.
- Register every invariant-mask experiment separately.
- Count every tested mask as part of multiple-testing correction.

---

### 5.3 P1-C — Self-supervised time-series embeddings

Compare existing LSTM/CNN learned embeddings against modern self-supervised time-series representations.

Initial candidates:

- TS2Vec-style hierarchical contrastive representation.
- PatchTST-style masked/patch self-supervised representation.
- Optional CoST-style trend/seasonality contrastive representation if implementation cost is acceptable.

Required outputs:

- `learned_ts2vec.parquet`
- `learned_patchtst_ssl.parquet`
- `ssl_embedding_report.md`
- `ssl_embedding_metadata.json`

Rules:

- Fit encoders on train only.
- Freeze encoders before validation.
- Do not fine-tune on Stage C.
- Treat each embedding family as a separate feature-engineering technique.
- Compare against existing LSTM/CNN embeddings and `tech_stat`, not only against weak baselines.

---

### 5.4 P1-D — Counterfactual/stress perturbation diagnostics

Implement controlled policy stress tests. These tests are diagnostic only and do not count as real trading evidence.

Recommended interventions:

- Set volatility regime to high.
- Increase OOD score.
- Shock spread/slippage proxy.
- Reduce volume/liquidity proxy.
- Perturb funding/carry features where available.
- Perturb regime probabilities.
- Remove or attenuate one feature family at a time.

Required outputs:

- `policy_stress_report.md`
- `policy_action_shift.parquet`
- `stress_scenario_config.yaml`
- `stress_summary_by_candidate.parquet`

Rules:

- Stress tests may identify fragility.
- Stress tests may not prove profitability.
- Stress tests may be used for kill decisions if the policy is obviously brittle under realistic conditions.

---

## 6. P2 implementation tasks — deferred research lane

Only start P2 after P0/P1 show real validation benefit or clear audit value.

Candidate P2 tasks:

1. Time-series foundation-model embeddings or critics.
2. MOMENT/Chronos-style embeddings as comparison features, not primary decision-makers.
3. Advanced causal-policy stress testing.
4. OPE support-overlap diagnostics for policy action distributions.
5. Causal RL/offline RL methods only after PPO/SAC/DQN baselines are reproducible and stable.

Rules:

- P2 must not interrupt current Stage A/B execution.
- P2 must not be used to rerun or tune Stage C.
- P2 must have its own pre-registration and multiple-testing accounting.

---

## 7. Required repository architecture

Add the following module structure to the `financial-data` repository. Adjust names only if they conflict with current repo conventions.

Recommended layout:

```text
financial_data/
  unsupervised/
    interfaces.py
    registry.py
    regime/
      hmm_regime.py
      gmm_regime.py
      kmeans_regime.py
    anomaly/
      mahalanobis_score.py
      knn_latent_score.py
      ae_reconstruction_score.py
      composite_ood.py
    representation/
      ts2vec_adapter.py
      patchtst_ssl_adapter.py
      embedding_dataset.py
    redundancy/
      feature_clustering.py
      feature_stability.py
    validation/
      split_guard.py
      leakage_checks.py
      regime_report.py
      ood_report.py
      feature_stability_report.py

  causal/
    interfaces.py
    registry.py
    granger_baseline.py
    pcmci_runner.py
    invariant_feature_selection.py
    counterfactual_stress.py
    leakage_audit.py
    graph_report.py

configs/
  unsupervised/
    ethusdt_4h_hmm.yaml
    ethusdt_4h_gmm.yaml
    ethusdt_4h_ood.yaml
    feature_redundancy_stagea_top.yaml
    ts2vec_stagea_top.yaml
    patchtst_ssl_stagea_top.yaml

  causal/
    ethusdt_4h_granger_audit.yaml
    ethusdt_4h_pcmci.yaml
    invariant_feature_selection_stagea_top.yaml
    causal_stress_ethusdt_4h_sac.yaml

features/
  trading_asset_features/
    <asset>/
      <timeframe>/
        unsup_regime.parquet
        unsup_ood.parquet
        feature_cluster_representatives.yaml
        causal_scores.parquet
        causal_feature_mask_candidates.yaml
        invariant_feature_scores.parquet

experiments/
  unsup_causal_audit/
    design/
    configs/
    runs/
    reports/
    graphs/
    feature_masks/
    evidence_packs/
    validation/
```

Required CLI commands:

```text
fd-unsup fit-regime --config <config_path>
fd-unsup score-ood --config <config_path>
fd-unsup feature-clusters --config <config_path>
fd-unsup validate --artifact-id <artifact_id>
fd-unsup export-features --artifact-id <artifact_id>

fd-causal granger-audit --config <config_path>
fd-causal fit-pcmci --config <config_path>
fd-causal invariant-score --config <config_path>
fd-causal stress-policy --run-id <rl_run_id> --config <config_path>
fd-causal validate --artifact-id <artifact_id>

fd-experiment register-unsup-causal-variant --config <config_path>
fd-experiment compare-paired-uplift --baseline-run <run_id> --variant-run <run_id>
```

Required interface principles:

- Every module must use explicit train/validation/held-out split contracts.
- Every fitted object must record fit period, input file hashes, config hash, code commit, seed, and `uses_heldout=false`.
- Every feature artifact must include metadata.
- Every generated feature file must be point-in-time aligned before RL consumption.
- Every variant must register into the immutable experiment ledger before training.

---

## 8. Metadata and artifact contract

Every unsupervised or causal artifact must include a metadata JSON with at least:

```json
{
  "artifact_type": "unsup_regime_features | unsup_ood_scores | causal_graph | invariant_feature_scores | feature_mask_candidate | policy_stress_report",
  "asset": "ethusdt",
  "timeframe": "4h",
  "fit_start": "<ISO timestamp>",
  "fit_end": "<ISO timestamp strictly before validation and before 2025-01-01>",
  "validation_start": "<ISO timestamp>",
  "heldout_start": "2025-01-01T00:00:00Z",
  "uses_heldout": false,
  "input_paths": [],
  "input_hashes": {},
  "model_class": "<class name>",
  "config_hash": "<sha256>",
  "code_commit": "<git sha>",
  "random_seed": 123,
  "output_paths": [],
  "leakage_checks_passed": true,
  "stage_c_firewall_passed": true
}
```

Also record:

- Dependency versions.
- Machine name.
- GPU lock usage if applicable.
- Runtime duration.
- Number of rows fitted.
- Number of rows transformed.
- Number of NaNs introduced.
- Number of rows dropped.
- Reason for every row drop.

---

## 9. Paired RL experiment design

For the first target, register the following paired variants:

Baseline:

- `A0`: SAC + ETHUSDT 4h + `tech_stat`

P0 variants:

- `A1`: SAC + ETHUSDT 4h + `tech_stat` + HMM/GMM regime probabilities
- `A2`: SAC + ETHUSDT 4h + `tech_stat` + OOD/anomaly scores
- `A3`: SAC + ETHUSDT 4h + `tech_stat` + regime probabilities + OOD/anomaly scores
- `A4`: SAC + ETHUSDT 4h + reduced feature-cluster representatives
- `A5`: SAC + ETHUSDT 4h + `tech_stat` + deterministic OOD risk overlay

P1 variants, only after P0 passes:

- `B1`: SAC + ETHUSDT 4h + causal mask candidate 1
- `B2`: SAC + ETHUSDT 4h + invariant feature mask candidate 1
- `B3`: SAC + ETHUSDT 4h + TS2Vec embeddings
- `B4`: SAC + ETHUSDT 4h + PatchTST SSL embeddings
- `B5`: SAC + ETHUSDT 4h + regime + OOD + invariant feature mask

Required comparison rules:

- Same train/validation split.
- Same RL algorithm configuration.
- Same seeds.
- Same cost/slippage assumptions.
- Same evaluation code.
- Same run-ledger schema.
- Same DSR/PBO/CSCV accounting policy.
- Report paired uplift, not isolated metrics.

Required metrics:

- Cost-adjusted return.
- Sharpe.
- Deflated Sharpe.
- Sortino.
- Calmar.
- Max drawdown.
- Turnover.
- Trade count.
- Win rate.
- Average trade expectancy.
- Slippage sensitivity.
- Seed variance.
- Regime-conditioned performance.
- Failure-case count.

Promotion criteria:

A variant may be promoted only if all of the following are true:

1. Real validation performance improves versus baseline after costs.
2. Improvement survives paired comparison.
3. Max drawdown improves or does not materially worsen.
4. Turnover does not materially worsen.
5. Slippage sensitivity does not materially worsen.
6. Seed variance decreases or remains acceptable.
7. DSR/PBO accounting does not flag the result as likely overfit.
8. The feature/artifact pipeline passes leakage checks.
9. The variant is frozen before Stage C.

Kill criteria:

Kill or quarantine a variant if any of the following occur:

1. Any post-2025-01-01 data is used before final held-out evaluation.
2. Any scaler, threshold, regime model, embedding model, causal graph, or feature mask is fitted on Stage C.
3. The variant improves raw returns only by increasing turnover or slippage fragility.
4. The result beats the baseline only in synthetic or stress evaluation.
5. The causal graph is unstable across folds and regimes.
6. OOD overlay silently removes too many trades without improving cost-adjusted validation metrics.
7. The variant cannot be reproduced under the same config hash and code commit.

---

## 10. Stage C firewall rules

The orchestrator must add explicit Stage C firewall assertions:

- No unsupervised model may fit on Stage C.
- No causal graph may fit on Stage C.
- No feature mask may be selected or modified using Stage C.
- No OOD threshold may be selected using Stage C.
- No self-supervised encoder may fit or fine-tune on Stage C.
- No synthetic generator may fit on Stage C.
- No LLM/agent prompt may include Stage C outcomes during design.
- No Stage C reruns are allowed for iteration.

Allowed Stage C usage:

- A single final evaluation of a frozen, promoted candidate.
- Artifact metadata must prove that the candidate was frozen before Stage C execution.

---

## 11. Best-practice engineering requirements

Implement the lane according to these software-engineering rules:

1. Keep all generators, scorers, graph learners, and validators behind explicit interfaces.
2. Use deterministic configs and stable artifact hashes.
3. Use typed config schemas where possible.
4. Fail closed on split violations.
5. Fail closed when a timestamp cannot be verified.
6. Fail closed on unknown feature availability semantics.
7. Do not silently impute or interpolate unless the original feature pipeline does the same and metadata records it.
8. All transformations must be fitted on train only.
9. Validation transformations may only call `transform`, never `fit`.
10. Every generated feature must have a provenance trail.
11. Every experiment variant must be registered before training.
12. Every report must include limitations and known failure modes.
13. Every heavy GPU job must use the existing GPU lockfile protocol.
14. Unit tests must cover split guards, metadata creation, deterministic hashes, no-heldout assertions, and feature alignment.
15. Integration tests must verify that `agent-multi` can load the new features without changing fixed PPO/SAC/DQN configs.

---

## 12. Required documentation updates

Update or create the following work-plan documents:

1. `work_plan/PHASE_3X_UNSUPERVISED_CAUSAL_AUDIT.md`
2. `work_plan/SOTA_INTEGRATION_DECISIONS.md`
3. `work_plan/30_PHASE_3_OVERVIEW.md`
4. `experiments/design/unsupervised_causal_audit.md`
5. `experiments/design/stage_c_firewall_assertions.md`
6. `experiments/design/multiple_testing_correction.md`, if new variants require explicit counting.
7. `features/README.md`, if new feature families are added.
8. `agent-multi` integration notes, if feature config schema needs new feature-family names.

Each document update must state that the lane is additive, controlled, and Stage-C-safe.

---

## 13. Required tests

Add tests for:

- Train/validation/held-out split enforcement.
- `2025-01-01` held-out boundary enforcement.
- No fitting on validation/held-out.
- Regime feature timestamp alignment.
- OOD score timestamp alignment.
- Causal parent lag enforcement.
- Metadata completeness.
- Artifact hash reproducibility.
- Agent-multi config export.
- Deterministic replay of a small example.
- Feature mask registration before RL training.
- Stage C firewall failure if unfrozen artifact is used.

---

## 14. Research references to include in the work plan

Use these references as technical background and implementation justification:

1. TS2Vec — hierarchical contrastive learning for time-series representation:
   - https://arxiv.org/abs/2106.10466

2. PatchTST — patch-based Transformer for long-term forecasting and self-supervised representation learning:
   - https://arxiv.org/abs/2211.14730

3. PCMCI+ — causal discovery for lagged and contemporaneous relations in time series:
   - https://arxiv.org/abs/2003.03685

4. Tigramite — Python package for causal time-series discovery and effect analysis:
   - https://jakobrunge.github.io/tigramite/
   - https://github.com/jakobrunge/tigramite

5. Invariant Risk Minimization — invariant predictors across environments:
   - https://arxiv.org/abs/1907.02893

6. MOMENT — open time-series foundation models, deferred P2 only:
   - https://arxiv.org/abs/2402.03885

7. Chronos — time-series foundation model direction, deferred P2 only:
   - https://arxiv.org/abs/2403.07815

8. Causality-inspired models for financial time-series forecasting, useful as a recent cautionary reference:
   - https://arxiv.org/html/2408.09960v1

Important interpretation:

- These references justify exploratory methods.
- They do not justify bypassing real validation.
- They do not justify using Stage C for tuning.
- They do not prove market causality.

---

## 15. Final orchestrator deliverable

After integrating this lane, produce a structured deliverable named:

`UNSUPERVISED_CAUSAL_AUDIT_INTEGRATION_DELIVERABLE.md`

The deliverable must include:

1. What documents were updated.
2. What tasks were added.
3. What tasks are P0/P1/P2.
4. Which artifacts are expected.
5. Which split/firewall rules were added.
6. Which tests were added.
7. How the first ETHUSDT 4h SAC + `tech_stat` comparison will run.
8. How variants will be counted for DSR/PBO/CSCV.
9. What is explicitly forbidden.
10. Remaining blockers or decisions that require Tier 4 human review.

End the deliverable with a clear go/no-go status for starting P0 implementation.
