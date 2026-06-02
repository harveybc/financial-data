# Phase 3X - Unsupervised Learning And Causal Audit Lane

**Status:** Approved as a narrow additive research/audit lane. Do not run as a broad matrix. Do not treat as a replacement for Phase 3 Stage A/B/C.

**Primary target:** `ETHUSDT 4h + SAC + tech_stat`, because it is the current strongest Stage A signal and has a clean feature table available for controlled tests.

---

## 1. Purpose

This lane tests whether train-only unsupervised and causal-audit artifacts improve robustness, feature quality, OOD awareness, and leakage detection for a small set of promising real-data candidates.

It may produce:

- regime features;
- OOD/anomaly scores;
- feature redundancy/stability reports;
- causal/leakage audit reports;
- candidate feature masks;
- policy stress diagnostics.

It may not produce:

- autonomous trading decisions;
- causal proof of alpha;
- unregistered feature changes;
- Stage C tuning decisions;
- broad new model-search grids.

The causal-audit target has been updated to match the business mechanic:
weekly retraining followed by one next-week trading interval. A causal unit is
not "one row predicts one far-future return." A causal unit is one target asset
at one weekly anchor, with a market-state window observed before the weekly
decision cutoff and a next-week outcome vector.

---

## 2. Entry Conditions

Phase 3X work may start only when:

1. A candidate has real-data Stage A evidence and a run-ledger record.
2. The candidate's train/validation/Stage C boundaries are declared.
3. The source feature table has timestamp columns and no post-`2025-01-01` rows in the train-fit slice.
4. The planned artifact is registered as audit-only or as a paired RL variant before training.

Exploratory tooling may be built earlier, but it cannot change Stage A/B rankings.

---

## 3. Core Rules

1. **Train-only fitting:** every scaler, clustering model, HMM/GMM, OOD estimator, causal graph, SSL encoder, threshold, and feature mask must be fitted only on the training split.
2. **Validation is transform-only:** validation data may be scored by train-fitted objects, but never used to fit or select thresholds.
3. **Stage C firewall:** no artifact may consume rows at or after `2025-01-01` before the final locked Stage C evaluation.
4. **Point-in-time feature alignment:** any feature unavailable before the environment decision must be shifted or excluded.
5. **Paired evidence only:** any feature addition, feature removal, OOD overlay, or mask is a registered paired variant against the matched real-only baseline.
6. **Multiple-testing accounting:** every tested artifact family, threshold, mask, and variant counts in DSR/PBO/CSCV-style reporting where feasible.
7. **Causal humility:** causal graphs and invariant scores are audit/hypothesis artifacts, not proof of tradeable causality.

---

## 4. P0 Tasks

### P0-A Train-Only Regime Features

Implement CPU-first HMM/GMM/K-means regime labeling for `ETHUSDT 4h + tech_stat`.

Required output features:

- `unsup_regime_id`
- `unsup_regime_prob_0..N`
- `unsup_regime_entropy`
- `unsup_regime_transition_prob`
- `unsup_regime_persistence`

Required reports:

- regime counts;
- transition matrix;
- train/validation regime-conditioned returns, volatility, drawdowns;
- metadata proving train-only fit and no Stage C usage.

### P0-B OOD/Anomaly Scores

Implement train-calibrated OOD scores:

- robust Mahalanobis distance;
- KNN distance in existing learned embedding space when available;
- regime entropy;
- missingness/liquidity anomaly score;
- composite OOD score.

An OOD exposure-reduction overlay is allowed only as a separate registered variant.

### P0-C Causal/Leakage Audit Baseline

Implement lag-only audit reports for selected features and future offline labels.

Required outputs:

- `causal_audit_report.md`
- `suspicious_features.parquet`
- `candidate_parent_scores.parquet`
- `timestamp_availability_audit.json`
- `feature_mask_candidates.yaml`

No feature is removed automatically.

The implemented weekly causal contract is:

```text
experiments/stage3x_market_state_causal_contract/
```

Role mapping:

- `patient`: target asset at a weekly anchor;
- `patient_state`: market-state description observed before the cutoff;
- `medicine`: input families, portfolio no-trade flags, exposure buckets, and
  supervisor settings defined before the cutoff;
- `outcome`: next-week market-status vector.

Default timing:

- 12-hour pretrade gap before the next-week outcome starts;
- 6-hour minimum gap for future experiments;
- 168-hour default lookback window;
- no Stage C rows and no post-cutoff features.

Allowed estimators are diagnostic only: blocked time-series cross-fit DML,
doubly robust learners, causal forests as diagnostics, invariant-risk screens,
and lag-only conditional-dependence screens.

Forbidden uses: causal-alpha proof, automatic feature deletion, validation
threshold tuning without trial accounting, and Stage C tuning.

### P0-D Feature Redundancy And Stability

Implement train-only feature clustering and stability reports:

- correlation and rank-correlation clustering;
- optional mutual-information screening;
- regime-conditioned feature stability;
- representative-feature candidates.

Reduced feature sets are candidate variants, not promotions.

---

## 5. P1 Tasks

Start only after P0 artifacts pass split and metadata tests.

- PCMCI+/Tigramite causal candidate-parent graphs.
- Invariant feature scoring across chronological folds and regimes.
- TS2Vec/PatchTST-style self-supervised embeddings as feature-family variants.
- Counterfactual/stress perturbation diagnostics.

P1 outputs remain diagnostic until paired real-validation RL results exist.

---

## 6. First Paired Variants

Baseline:

- `A0`: `SAC + ETHUSDT 4h + tech_stat`

P0 variants:

- `A1`: `A0 + regime probabilities`
- `A2`: `A0 + OOD scores`
- `A3`: `A0 + regime probabilities + OOD scores`
- `A4`: `SAC + ETHUSDT 4h + feature-cluster representatives`
- `A5`: `A0 + deterministic OOD exposure-reduction overlay`

Promotion requires real validation improvement under matched seeds, costs, split, algorithm config, and action/reward settings.

---

## 7. Required Artifacts

Store artifacts under:

```text
experiments/unsup_causal_audit/
features/trading_asset_features/<asset>/<timeframe>/
configs/unsupervised/
configs/causal/
```

Every fitted artifact must include metadata:

- artifact type;
- asset/timeframe;
- fit start/end;
- validation start/end;
- heldout start `2025-01-01T00:00:00Z`;
- `uses_heldout=false`;
- input hashes;
- config hash;
- code commit;
- random seed;
- output paths;
- leakage checks.

---

## 8. Go/No-Go

**Go for P0 documentation and narrow tooling.**

**No-go for broad execution** until the following are available:

1. split-guard tests;
2. artifact metadata schema;
3. feature alignment checks;
4. paired-variant registration;
5. a small ETHUSDT 4h smoke artifact that proves train-only fitting.

Current implementation status: the weekly market-state causal contract is
available as a CPU-only worker and passes its tests. It does not unlock Stage C
and does not launch training. It is ready to feed the Stage 3X optimizer as a
diagnostic/context contract once cross-asset data contracts are expanded.
