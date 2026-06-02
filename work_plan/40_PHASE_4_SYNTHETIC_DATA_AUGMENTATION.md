# Phase 4 - Synthetic Data Augmentation And Robustness Testing

**Status:** Deferred optional phase. Do not start until the weekly-retrained
real-data pipeline has auditable repeated walk-forward evidence.

2026-05-23 update: Phase 4 is not part of the current unblocking path.
Synthetic data must not be used to rescue weak real-data evidence, hide
no-trade/overtrade behavior, or replace weekly walk-forward validation. The old
one-off synthetic research prompts were archived under
`archive_superseded_2026_05_23_weekly_data_first/`.

**Purpose:** Test whether synthetic financial OHLCV data can improve downstream Project 3 policies through augmentation, pretraining, or stress-scenario exposure without weakening the real-data evidence standard.

---

## 1. Entry Conditions

Phase 4 may start only after:

1. Weekly walk-forward real-data anchors are registered in the immutable run
   ledger.
2. Simple baseline comparisons exist for candidate weekly streams.
3. Feature-family/source-family ablation evidence exists for candidate streams.
4. Leakage and heldout firewall audits pass for the candidate training inputs.
5. Real-data-only candidate configurations are identified.
6. Broker/trade-frequency/Friday-force-close policies pass mechanically.
7. The 2025 heldout period remains untouched except for final locked evaluation.

If any of those are missing, synthetic-data work is exploratory tooling only and cannot influence promotion.

---

## 2. Core Rule

Synthetic data may augment training, but real data remains the judge.

A synthetic-augmented configuration is useful only if it beats the matched real-data-only configuration on real validation data under the same:

- asset
- timeframe
- feature preset
- algorithm
- seed set
- train/validation split
- cost scenario
- reward/action configuration

Synthetic-only metrics are diagnostic. They are not promotion evidence.

---

## 3. Stage 4.1 - Synthetic Generator Tooling

**Goal:** Build or adapt a plugin-first synthetic OHLCV generator that can consume Project 3 model-ready inputs safely.

**Primary prompt:** no active prompt. Draft a fresh spec only after Phase 4
entry conditions pass.

**Required behavior:**

- Generate primitive OHLCV paths first.
- Recompute `typical_price` and deterministic technical/statistical features after reconstruction.
- Enforce OHLC constraints by construction.
- Fit all transforms/generators on train-only data.
- Reject data on or after `2025-01-01` in Project 3 mode.
- Emit metadata with input hashes, config hash, train window, generator family, seed, and augmentation ratio.

**Minimum accepted generator:**

- Moving-block or stationary bootstrap over transformed OHLCV primitives.

**Optional later generators:**

- Regime-conditional bootstrap.
- GARCH/EGARCH/GJR-style financial baseline.
- TimeVAE or time-causal VAE.
- TimeGAN, COT-GAN, Sig-Wasserstein GAN.
- Financial diffusion models.

---

## 4. Stage 4.2 - Synthetic Quality Evaluation

**Goal:** Reject generators that create invalid, memorized, or statistically useless data before any downstream RL experiment.

Required evaluator families:

1. Algebraic validity:
   - positive prices
   - nonnegative volume
   - `HIGH >= max(OPEN, CLOSE)`
   - `LOW <= min(OPEN, CLOSE)`
   - `typical_price` recomputation consistency

2. Stylized financial facts:
   - return distribution
   - fat tails
   - volatility clustering
   - return autocorrelation
   - squared/absolute return autocorrelation
   - drawdown distribution
   - volume distribution
   - volume-volatility relationship

3. Distributional distance:
   - KS distance
   - Wasserstein distance
   - ACF distance
   - MMD over windows, if feasible
   - drawdown-distribution distance

4. Memorization checks:
   - duplicate-window count
   - nearest-neighbor window distance
   - longest copied subsequence
   - real-vs-synthetic classifier AUC

---

## 5. Stage 4.3 - Downstream Utility Ablation

**Goal:** Test whether synthetic augmentation improves real validation performance.

Required matched experiments:

- `real_train_only`
- `synthetic_train_only`
- `real_plus_synthetic_0_25x`
- `real_plus_synthetic_0_50x`
- `real_plus_synthetic_1_00x`
- `synthetic_pretrain_then_real_finetune`

Required report fields:

- candidate run id
- generator family
- generator config hash
- augmentation ratio
- downstream algorithm
- seed set
- real validation metrics
- cost scenario
- comparison against matched real-only baseline
- whether the synthetic variant beats the real-only baseline
- whether improvement survives pessimistic costs

---

## 6. Promotion Policy

Synthetic augmentation may be promoted to a Phase 3 candidate only if:

1. Generator training used only the candidate training window.
2. Synthetic data passed algebraic validation with zero OHLC violations.
3. Memorization checks do not indicate copied windows.
4. Augmented policy beats the matched real-only baseline on real validation data.
5. Improvement is not concentrated in one seed.
6. Improvement survives base cost and does not collapse under pessimistic cost.
7. No Stage C/2025 heldout data was used for generator selection.

If these conditions are not met, synthetic data remains a diagnostic/stress-test tool only.

---

## 7. Explicit Non-Goals

- Do not use synthetic data to manufacture more heldout data.
- Do not use synthetic data to hide weak real-data evidence.
- Do not tune synthetic generators on 2025 heldout performance.
- Do not directly generate indicator columns as independent variables.
- Do not start with GAN/diffusion complexity before bootstrap baselines and evaluators are correct.


---

## 8. Refinements (post-review)

The following twelve refinements harden the protocol and were folded into the Stage 4 implementation in `synthetic-datagen` (Stages 4.1–4.3) and into the matched-experiment manifests consumed by `predictor` and `agent-multi`. They MUST be respected by any future generator family.

1. **Numerical pass/fail gates are explicit and code-enforced.** §4.2 gates use these thresholds: `ks_pvalue_min = 0.01`, `wass_ratio_max = 1.5` (synthetic-vs-real Wasserstein-1 over log-returns, normalized by the real-vs-real bootstrap split baseline), `classifier_auc_max = 0.70`, `duplicate_window_rate_max = 1e-3`, `max_nn_overlap_rate_max = 1e-3` (cosine ≥ 0.95 over fixed-length return windows), `copied_subseq_ratio_max = 0.50` (longest copied consecutive-NN run / window). These are encoded in `FinancialDistributionEvaluator` and `MemorizationEvaluator` and surfaced in their `gates` dict.

2. **Generator-family registry.** Every generator carries an immutable `generator_family_id` (e.g. `stationary_bootstrap_v1`) and a `synthetic_ablation_id` (e.g. `ratio_1_00x`). These IDs appear in the audit record, on every produced row of the synthetic ledger, and on every Stage 4.3 manifest. Promotion-decision lookups MUST key on `(asset_id, timeframe, generator_family_id, generator_config_hash)`.

3. **Memorization tripwires are mandatory, not advisory.** Stage 4.2 auto-rejects a generator family if any of (a) duplicate-window rate > 1e-3, (b) NN cosine-overlap rate > 1e-3, or (c) longest copied subsequence ratio > 0.50, even if distribution gates pass. The classifier-AUC gate is independent of these.

4. **Augmentation-ratio semantics are fixed.** A ratio of 0.5x means "for every 2 real rows, append 1 synthetic row, in causal time order, with `synthetic_origin=1` flag preserved end-to-end." The downstream replay buffer or sampler MAY weight synthetic rows differently, but the flag MUST NOT be erased.

5. **Multi-cost-scenario rule.** A synthetic-augmentation run is promoted only if it beats the matched real-only baseline under BOTH `base` AND at least one pessimistic cost scenario (`plus_50pct` or `plus_100pct`). Each Stage 4.3 manifest is emitted three times (one per cost scenario) precisely to make this auditable.

6. **Diagnostic-only exit ramp.** If after Stage 4.2 a generator family fails any §4.2 gate, it MAY still be retained as a diagnostic/stress-test tool (Phase 5/6 robustness) but is permanently barred from contributing to a real-deployment training mix. This must be recorded on its synthetic-ledger row (`valid = false`) and the family ID added to the project-level `synthetic_diagnostics_only.txt` register.

7. **Ledger mirror.** Every fit, generate, and evaluate call writes one row to `experiments/synthetic_data/SYNTHETIC_LEDGER.csv` with columns `(timestamp_utc, kind, config_hash, git_commit, asset_id, timeframe, generator_family_id, synthetic_ablation_id, trainer, generator, evaluator, seed, train_start, train_end, heldout_boundary, project3_mode, synthetic_use_case, augmentation_ratios, model_file, output_file, metrics_file, n_rows, valid, notes)`. Implemented in `app/synthetic_ledger.py`.

8. **Selection-leakage rule (`forbidden_paths.txt`).** Stage 4.2 evaluators and the Stage 4.3 generator-selection logic MUST refuse to open any file matching a glob in `forbidden_paths.txt` (default: `*/heldout/2025/*`, `*/2025_heldout/*`, `*/stage_c/*`). Implemented in `app/forbidden_paths.py` and called from the trainer’s data-reader.

9. **Statistical power floor.** Each ablation cell is run with at least 5 seeds (`seeds = [0, 1, 2, 3, 4]` in the default manifest). Promotion (§5.6) requires (a) the median seed beats the matched real-only baseline AND (b) the improvement is not concentrated in a single seed (top-seed-minus-median improvement ≤ 50 % of total improvement).

10. **Smoke stage 4.1.5.** A 1-day synthetic generation run on a tiny window (≤ 200 rows) MUST be checked into the ledger before Stage 4.2 evaluators are unlocked. The smoke run validates that `OhlcvAlgebraicEvaluator` returns zero violations and that audit metadata is non-empty. The CI gate for Phase 4 should include this smoke.

11. **Cross-repo plugin contract.** All Phase 4 plugins follow the predictor-style contract: class-level `plugin_params: dict`, `set_params(**kw)`, `__init__(self, config: Optional[Dict[str, Any]] = None)`. Entry-point groups: `sdg.trainer`, `sdg.generator`, `sdg.evaluator`, `sdg.optimizer`, `sdg.transformer`, `sdg.reconstructor`, `sdg.feature_engine`, `sdg.aggregator`, `sdg.pipeline`. This guarantees that a plugin written for `synthetic-datagen` can also be loaded by `predictor`’s and `agent-multi`’s plugin loaders without modification.

12. **Protocol-doc stub.** A short `docs/synthetic_data_protocol.md` should accompany each `generator_family_id` introduction, recording the family’s mathematical assumptions, the windows it was fit on, the §4.2 gate values it produced, and the cells (Stage 4.3) it has been authorized for. The Stage 4.3 orchestrator emits a stub at the top of `experiments/synthetic_data/<family>/ablation_index.json` to seed this document.

---

## 9. Post-Implementation Audit Notes - 2026-05-03

The first `synthetic-datagen` implementation correctly established a useful plugin path for primitive-first OHLCV generation, causal `tech_stat` recomputation, audit metadata, and a stationary-bootstrap baseline. However, the first Project 3 ETHUSDT 4h generated dataset is **not valid for policy training**.

Audit findings:

1. The generator fit window was clean: `2017-09-28 04:00:00` through `2021-09-27 20:00:00`, with zero rows at or after the Project 3 Stage C boundary.
2. The staged source file contained `2025-01-01+` rows. This is acceptable only as raw source storage; augmented training panels must not include those rows.
3. The first augmented CSV included rows through `2025-12-31 20:00:00`; this violated the Phase 4 safety expectation for generated Project 3 training panels.
4. The stationary-bootstrap sample passed algebraic and return-distribution gates, but failed memorization gates:
   - `duplicate_window_rate = 0.025` versus max `0.001`
   - `nn_overlap_rate = 0.01` versus max `0.001`
   - `copied_subseq_ratio = 2.46875` versus max `0.50`
5. Because memorization gates failed, the downstream SAC augmented run is invalid as training evidence and must be treated as diagnostic-only.

Corrections applied:

1. `build_augmented_project3_training.py` now uses `PROJECT3_HELDOUT_BOUNDARY = 2025-01-01 00:00:00`.
2. Project 3 augmented panels are limited to real rows strictly before `2025-01-01`.
3. Algebraic, distribution, and memorization gates are fatal by default.
4. The script appends an explicit `evaluate` row to `SYNTHETIC_LEDGER.csv` with `valid=false` when gates fail.
5. If gates fail, stale augmented training CSVs are quarantined with `.invalid_quality_gates`.

Operational rule:

> No `synthetic-datagen` output may be consumed by `agent-multi`, `predictor`, or Project 3 training unless its `augmentation_summary.json` has `project3_valid_for_training = true` and the synthetic ledger row for the generator/evaluator pair has `valid = true`.

Current decision:

- `stationary_bootstrap_v1` remains useful as a P0 diagnostic and baseline generator.
- The current ETHUSDT 4h stationary-bootstrap artifact is **diagnostic-only**, not a training dataset.
- Next acceptable implementation target is a stricter non-overlapping block/bootstrap variant or regime-conditioned residual bootstrap that can pass memorization gates before any SAC/PPO/DQN augmentation run is launched.
