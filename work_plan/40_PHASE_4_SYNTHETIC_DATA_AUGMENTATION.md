# Phase 4 - Synthetic Data Augmentation And Robustness Testing

**Status:** Deferred optional phase. Do not start until Phase 3 Stage A/B governance is producing auditable promotion packets.

**Purpose:** Test whether synthetic financial OHLCV data can improve downstream Project 3 policies through augmentation, pretraining, or stress-scenario exposure without weakening the real-data evidence standard.

---

## 1. Entry Conditions

Phase 4 may start only after:

1. Phase 3 Stage A results are registered in the immutable run ledger.
2. Simple baseline comparisons exist for candidate runs.
3. Feature-family/source-family ablation evidence exists for candidate runs.
4. Leakage and heldout firewall audits pass for the candidate training inputs.
5. Real-data-only candidate configurations are identified.
6. The 2025 heldout period remains untouched except for final locked evaluation.

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

**Primary prompt:** `SYNTHETIC_DATAGEN_SPECKIT_COPILOT_PROMPT.md`

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

