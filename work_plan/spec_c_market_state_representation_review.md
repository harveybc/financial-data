# Spec C Execution Memo — Project 3 Market-State Representation Review

**Prepared for:** Project 3 weekly-retrained portfolio/RL trading system  
**Scope executed:** ChatGPT 5.5 Pro Web Spec C only  
**Date:** 2026-05-25  

---

## 1. Scope and hard constraints

This memo executes **Spec C only**: external research review, no code mutation, no Stage C unlock, no broad GPU work, and no PPO/SAC/DQN algorithm-source edits.

The uploaded agent-spec document defines Spec C as a research review of the proposed market-state representation families for **1h and 4h weekly decision windows**, including:

- engineered summaries;
- PCA / robust PCA;
- autoencoders;
- TS2Vec / contrastive embeddings;
- PatchTST / masked patch embeddings;
- regime probabilities;
- hybrid profiles.

The correct business target is not a static one-year model. It is a **weekly-retrained production loop**: train/update through the completed week, trade only the next week, allocate under a portfolio supervisor, and aggregate evidence across repeated weekly walk-forward anchors.

A single positive week must remain optimizer feedback, not tradability proof.

The current causal contract is mechanically clean but tiny:

- `stage_c_access = DENIED`
- `training_launched = false`
- `pretrade_gap_hours = 12`
- `lookback_hours = 168`
- `state_encoding_mode = window_summary`
- `rows = 12`
- `temporal_issue_count = 0`

This is enough to prove contract mechanics. It is **not enough** to select learned embeddings on profitability grounds.

---

## 2. Main recommendation

Prioritize **low-dimensional, train-only, CPU-screened representations** before any learned encoder:

1. **Engineered window summary** as the mandatory baseline for both 1h and 4h.
2. **Engineered + regime probabilities** for 4h first, then 1h.
3. **Engineered + PCA / IncrementalPCA** for 1h first, then 4h.
4. **Engineered + OOD/anomaly scores** as risk-overlay/context features, not alpha proof.
5. **Small hybrid selected profile** only after redundancy screening.
6. **Autoencoder** only as a controlled nonlinear compression experiment.
7. **TS2Vec** only after the above pass validation-safe diagnostics.
8. **PatchTST / masked patch embedding** last; it is the least urgent for the current 168h weekly-window contract, especially for 4h windows.

This ordering matches the project’s own CPU-first/GPU-second rule: learned state encoders must beat engineered/PCA baselines in split-safe diagnostics before consuming SAC smoke GPU time.

---

## 3. Ranked recommendation table

| Rank | Profile family | 1h priority | 4h priority | Recommendation | Why |
|---:|---|---:|---:|---|---|
| 1 | **Engineered summary** | Very high | Very high | Implement/keep as reference baseline | Highest interpretability, lowest leakage surface, cheapest to hash/reproduce, directly aligned with the 168h cutoff window. |
| 2 | **Engineered + regime probabilities** | Medium-high | Very high | Implement early | Regime probabilities add compact context without forcing a deep encoder. Use KMeans/GMM first; HMM only if sequence persistence adds value. |
| 3 | **Engineered + PCA / IncrementalPCA** | Very high | Medium-high | Implement early | 1h windows have more bars and more redundancy; PCA is a cheap compression baseline. scikit-learn PCA uses SVD after centering, while IncrementalPCA supports minibatch-style decomposition for larger data. |
| 4 | **OOD/anomaly context** | High | High | Use as risk/supervisor context first | The audit lane already allows Mahalanobis/KNN/regime-entropy/missingness OOD scores, but exposure reduction must be a separate registered variant. |
| 5 | **Small selected hybrid** | Medium | Medium | Use only after redundancy screen | Hybrid is useful only if it combines nonredundant families. A “full concatenation” profile is likely to overfit and destabilize SAC observations. |
| 6 | **Autoencoder** | Medium | Low-medium | Defer until CPU profiles pass | Useful for nonlinear compression, but reconstruction quality does not imply trading value. Keep undercomplete, deterministic, and paired against engineered/PCA. |
| 7 | **TS2Vec / contrastive embedding** | Medium | Low-medium | Defer, then try 1h before 4h | TS2Vec is designed for timestamp/subsequence representation through hierarchical contrastive learning and reported broad time-series representation results, but those results are not trading-profit evidence. |
| 8 | **PatchTST / masked patch embedding** | Low-medium | Low | Last learned-encoder candidate | PatchTST’s core design is patched subseries tokens and channel independence for transformer time-series modeling; this is more attractive for longer 1h windows than short 4h weekly windows. |

---

## 4. Critique of each proposed state profile

### 4.1 Engineered summary

This should remain the **canonical baseline**. For a 168h lookback, use features that summarize what the supervisor would plausibly know before cutoff:

- realized volatility;
- downside volatility;
- return quantiles;
- drawdown over lookback;
- trend slope;
- momentum decay;
- liquidity/spread proxy;
- correlation to selected cross-assets;
- lead/lag summaries;
- event-calendar risk counts;
- recent strategy health.

For 4h, the 168h window is only about 42 bars, so engineered summaries are often more statistically reliable than deep encoders. For 1h, the 168 bars give enough granularity for intraday volatility/liquidity summaries while staying compact.

Main risk: if engineered features are hand-selected after looking at next-week performance, they become a silent optimizer. Every summary family must be registered, hashed, and trial-counted under the existing multiple-testing rule.

### 4.2 PCA / robust PCA

PCA is the best first compression baseline for 1h because it can reduce redundant volatility/trend/cross-asset columns before SAC sees them. It should be fitted **train-only**, then applied transform-only to validation/test. The audit spec explicitly requires train-only fitting for scalers, clustering models, OOD estimators, SSL encoders, thresholds, and feature masks; validation may only be transformed/scored.

Use ordinary PCA/IncrementalPCA first. Avoid treating “robust PCA” as a magic improvement. scikit-learn’s robust covariance `MinCovDet` is intended for Gaussian or unimodal symmetric distributions and warns that it is not meant for multi-modal data. Since market regimes are often multi-modal, robust covariance is better used as an **OOD score component** than as the primary global representation.

Recommended PCA profile variants:

1. `engineered + robust_scaler + PCA(n_components by train variance cap)`
2. `engineered + robust_scaler + PCA(fixed small k: 4, 8, 12)`
3. `engineered + IncrementalPCA` only if memory or rolling recomputation becomes a bottleneck.

Do not use PCA whitening by default; it can erase economically meaningful relative scale unless explicitly compared as a registered preprocessing profile.

### 4.3 Autoencoder

A small undercomplete autoencoder can capture nonlinear interactions that PCA misses, but it is easy to overfit a tiny weekly-anchor setting. Use it only after engineered/PCA/regime profiles establish CPU-screen baselines.

Minimum safe design:

- undercomplete bottleneck: 4–16 dimensions;
- no target labels;
- train-only fit;
- validation/test transform-only;
- deterministic seeds;
- early stopping based only on train/internal split, not Stage C;
- artifact hash for architecture, weights, scaler, input columns, and output columns.

Avoid denoising or masking schemes that accidentally use future-bar reconstruction targets across the decision cutoff. For this project, autoencoder output is a **candidate state descriptor**, not a trading signal.

### 4.4 TS2Vec / contrastive embedding

TS2Vec is a credible learned-representation candidate because it learns contextual timestamp-level representations and can aggregate timestamp representations into subsequence representations. It is better aligned with the 1h window than with 4h because 168 one-hour observations give more temporal structure than roughly 42 four-hour observations.

Main risks:

- augmentations can destroy financial semantics;
- learned embeddings can encode missingness/calendar artifacts rather than market state;
- validation-safe improvements may be from volatility clustering, not tradable edge;
- contrastive pretraining can become a hidden broad experiment if many augment/window/temperature settings are tried.

Use TS2Vec only after a selected engineered/PCA/regime shortlist exists, and send only one or two profiles to GPU smoke.

### 4.5 PatchTST / masked patch embedding

PatchTST is a transformer-style design built around segmenting a time series into subseries patches and using channel independence. That makes it attractive for long-sequence forecasting/representation, but less compelling as an immediate step for 4h weekly windows, where 168h gives only about 42 samples.

PatchTST should be last because it introduces heavier dependency, tuning, and GPU pressure. If used, it should be attempted on 1h first with a tiny patch grid, fixed architecture, and strict artifact registration. The official implementation notes that PatchTST is included in larger ecosystem packages such as GluonTS, NeuralForecast, and tsai, but those packages should not be introduced unless the project has already selected PatchTST as worth the dependency cost.

### 4.6 Regime probabilities

Regime probabilities are high-value because they are compact, interpretable, and naturally compatible with the portfolio supervisor. The audit lane already calls for train-only HMM/GMM/KMeans regime labeling with:

- `unsup_regime_id`
- `unsup_regime_prob_0..N`
- `unsup_regime_entropy`
- `unsup_regime_transition_prob`
- `unsup_regime_persistence`
- regime-conditioned diagnostics

Recommended order:

1. KMeans with multiple deterministic restarts for cheap mechanical baseline.
2. GaussianMixture for soft probabilities and covariance-aware regimes.
3. HMM only after KMeans/GMM diagnostics show regime persistence matters.

KMeans is fast but can fall into local minima, so multiple seeds/restarts are mandatory. GaussianMixture provides probabilistic cluster membership and covariance structure, which is more useful for soft regime context. hmmlearn is viable for HMMs, but its GitHub page states it is in limited-maintenance mode, so it should be optional rather than a core dependency.

### 4.7 Hybrid full

A full hybrid profile is dangerous if it means concatenating everything. It will increase observation dimensionality, redundancy, and multiple-testing burden. The only acceptable hybrid is a **selected hybrid**:

- engineered summary core;
- either PCA or regime, not both unless nonredundant;
- OOD score as risk context;
- learned embedding only if it passes CPU diagnostics;
- maximum feature budget enforced.

A hybrid profile should win because it improves net risk-adjusted weekly behavior after costs, not because it has the most information.

---

## 5. Minimum implementation order

### 5.1 Shared prerequisites for both 1h and 4h

1. Lock the causal-unit schema:
   - `target_asset`
   - `anchor_week`
   - observation window
   - cutoff
   - outcome window
   - feature columns
   - hashes
   - scaler/encoder hashes
   - stage access
   - temporal issue count
2. Enforce `pretrade_gap_hours = 12` by default, with 6h as the absolute minimum only for explicitly registered experiments.
3. Reject any non-Stage-C artifact containing rows at or after `2025-01-01`.
4. Keep the current profile-worker requirement:
   - emit engineered summary, engineered+PCA, engineered+regime first;
   - include autoencoder/TS2Vec/Patch stubs without heavy dependencies;
   - rank with validation-safe diagnostics and negative controls.

### 5.2 4h implementation order

1. **4h engineered summary**
2. **4h engineered + KMeans/GMM regime probabilities**
3. **4h engineered + PCA**
4. **4h engineered + OOD score bundle**
5. **4h selected hybrid: engineered + best one of regime/PCA + OOD**
6. **4h autoencoder only if selected hybrid still leaves nonlinear residual value**
7. **4h TS2Vec/PatchTST only if 1h learned embeddings prove useful first**

Rationale: 4h has fewer time steps per 168h window, so compact summaries and regime probabilities are more likely to be stable than transformer-style patches.

### 5.3 1h implementation order

1. **1h engineered summary**
2. **1h engineered + PCA / IncrementalPCA**
3. **1h engineered + KMeans/GMM regime probabilities**
4. **1h engineered + OOD score bundle**
5. **1h selected hybrid**
6. **1h small autoencoder**
7. **1h TS2Vec**
8. **1h PatchTST**

Rationale: 1h has enough observations per weekly state window to make compression/representation learning more plausible, but the learned encoders should still follow CPU diagnostics.

---

## 6. Redundant or low-value experiments to avoid

1. **PatchTST on 4h before 1h.** The 4h weekly window is short, so patching likely adds architecture risk before evidence.
2. **Robust PCA before ordinary PCA.** Robust covariance assumptions are fragile in multi-regime markets; use robust methods as anomaly diagnostics first.
3. **HMM with many hidden states on tiny anchor sets.** Regime labels will be unstable and can create false interpretability.
4. **Full hybrid concatenation.** This inflates feature count, redundancy, and SAC observation instability.
5. **Validation-tuned OOD thresholds without trial accounting.** The audit spec forbids validation threshold tuning without multiple-testing accounting.
6. **Learned encoders trained or selected using next-week labels.** That converts representation learning into hidden supervised optimization.
7. **Event-calendar features using actual-vs-forecast reactions before the decision time.** The protocol requires event features to be known/lagged at decision time and treats the first event-calendar layer as a risk overlay, not a magic alpha source.
8. **Portfolio allocation libraries as opaque truth.** Riskfolio-Lib and PyPortfolioOpt are acceptable reference engines, but the project’s own evidence contract and weekly simulator must remain authoritative.

---

## 7. Lightweight dependencies

### 7.1 Recommended core dependencies

Use what is already aligned with CPU-first screening:

- **scikit-learn** for PCA, IncrementalPCA, KMeans, GaussianMixture, robust covariance/OOD, scalers, and deterministic pipeline-style transforms.
- **NumPy / pandas / SciPy** as existing numerical foundations.
- **statsmodels** only if classical time-series diagnostics are needed; its `tsa` module includes AR, VAR, ARMA, and Markov-switching-related time-series tooling.

### 7.2 Optional dependencies

- **hmmlearn** for HMM regime tests, but only as optional because the project page indicates limited maintenance.
- **PyPortfolioOpt** or **Riskfolio-Lib** as CPU reference tools for HRP/risk-parity/CVaR-style allocations, not as a replacement for the project’s own evidence contract.

### 7.3 Avoid for now

Avoid adding GluonTS, NeuralForecast, tsai, PyTorch Lightning, or transformer stacks until a learned profile passes CPU diagnostics and is explicitly selected for GPU smoke. PatchTST’s ecosystem availability is useful later, but importing the ecosystem early will increase dependency and reproducibility risk.

---

## 8. Failure modes and negative controls

### 8.1 Failure modes

1. **Temporal leakage at the weekend boundary**: feature includes post-cutoff rows or revised values.
2. **Stage C contamination**: any non-final artifact touches rows at or after `2025-01-01`.
3. **Representation overfitting**: encoder performs well on one anchor bundle but fails across regimes.
4. **Cost blindness**: profile improves gross return but worsens cost-to-gross-edge ratio.
5. **Regime label instability**: cluster identities flip across weekly retrains.
6. **Dimensionality explosion**: hybrid profile increases observation dimension enough to destabilize SAC.
7. **OOD threshold overfit**: OOD overlay reduces exposure only because thresholds were tuned on validation outcomes.
8. **Cross-asset availability mismatch**: features from another market are unavailable at the target asset’s decision cutoff.
9. **No-trade false success**: risk overlay avoids losses by suppressing all trades.
10. **Always-in-market false success**: profile improves trend capture in one regime but violates trade-rate or exposure policy.
11. **Portfolio covariance error**: allocation is based on raw asset correlation instead of strategy-stream correlation.
12. **Future-leak sentinel not detected**: the screening layer cannot distinguish impossible future information from legitimate state.

### 8.2 Required negative controls

The profile-screen worker already requires shuffled outcome, future-leak sentinel, irrelevant feature family, redundancy reporting, deterministic hashes, and selected nonredundant shortlist behavior. Add these controls explicitly:

1. **Shuffled next-week outcome**: real profiles must not show stable improvement.
2. **Circularly shifted state windows**: breaks timing while preserving distributions.
3. **Future-leak sentinel**: deliberately constructed future-return feature must be detected/blocked, not selected.
4. **Random regime labels with matched frequency**: should lose to real regime probabilities.
5. **Irrelevant asset family**: unrelated synthetic or irrelevant cross-asset features should not rank.
6. **Cost-stress control**: profile must not rely on edge smaller than plausible slippage/spread.
7. **No-trade control**: compare against deterministic no-trade and equal-risk no-trade overlays.
8. **Always-trade control**: detect profiles that simply increase exposure.
9. **Seed-stability control**: repeated profile generation must preserve hashes or report deterministic differences.
10. **Stage C injection test**: injected post-`2025-01-01` row must fail closed.

---

## 9. Exact criteria for sending a profile to GPU smoke

A profile should be eligible for **one small config-gated SAC GPU smoke**, not broad GPU work, only if all criteria below pass.

### 9.1 Mechanical gates

1. `stage_c_access == "DENIED"`.
2. `training_launched == false` in profile-generation artifacts.
3. No rows at or after `2025-01-01` in any non-Stage-C artifact.
4. Cutoff gap is 12h by default; any 6h experiment must be explicitly registered.
5. Every scaler, PCA, clusterer, OOD estimator, autoencoder, TS2Vec encoder, or PatchTST encoder is train-fit only.
6. Validation/test are transform-only.
7. Source columns, selected columns, encoder config, scaler config, artifact output, and observation fields all have deterministic hashes.
8. Negative controls fail as expected.
9. The profile is present in observation evidence with `market_state_profile_id` and `market_state_profile_hash`.
10. No PPO/SAC/DQN algorithm source changes are required.

### 9.2 Statistical/practical gates

Use these as the initial Stage 3X GPU-smoke gate:

1. **Minimum evidence size**: at least 24 weekly causal units for preliminary GPU-smoke eligibility; the current 12-row fixture is mechanical-only.
2. **Baseline comparison**: profile must beat both engineered summary and engineered+PCA/regime baseline on validation-safe score.
3. **Effect size**: validation-safe composite score improves by at least **5%** over the best CPU baseline, or improves by at least **2%** while reducing feature count by at least **30%**.
4. **Probability of improvement**: blocked bootstrap or anchor-level sign test gives `P(profile > baseline) >= 0.60`.
5. **Risk non-degradation**: weekly CVaR and max drawdown are not worse than baseline by more than **5%**.
6. **Cost discipline**: cost-to-gross-edge ratio is not worse than baseline by more than **10%**.
7. **Trade policy**: no hard trade-frequency, Friday-late-exposure, force-flat, or broker-policy violation.
8. **Nonredundancy**: profile has `max_abs_corr < 0.90` to any selected profile, or, if redundant, it must improve composite score by at least **5%**.
9. **Seed stability**: for learned encoders, three encoder seeds produce the same selected profile family and a coefficient of variation of the screen score below **1.0**.
10. **Capacity discipline**: only the best one learned profile per timeframe may go to GPU smoke in a generation.

### 9.3 GPU-smoke interpretation rule

A passing GPU smoke is not a promotion. It only means the profile is eligible to become a registered Stage 3X candidate for repeated weekly walk-forward evaluation. Stage B promotion still requires cost scenarios, seeds, baselines, statistical gates, and no Stage C rows.

---

## 10. Implementation risks

1. **The current 12-row causal fixture is too small for learned profile ranking.** Use it for contract tests, not learned-encoder selection.
2. **The standalone market-state representation optimization plan and latest G15 synthesis summary were not included in the uploaded files used for this memo.** Therefore, this memo does not assert exact G15 metrics or plan-specific thresholds beyond what appears in the uploaded protocol/spec excerpts.
3. **Literature success is not trading success.** TS2Vec and PatchTST are credible representation methods, but their published results are not evidence of costed next-week trading profitability.
4. **Robust covariance can be misapplied.** Market-state distributions are commonly multi-regime; use robust Mahalanobis as an OOD component, not as a universal robust representation.
5. **Library adoption can outpace evidence.** Keep deep-learning/time-series packages out until a profile passes CPU diagnostics and negative controls.

---

## 11. Final recommendation

Proceed with **engineered summary, engineered+regime, engineered+PCA, and OOD context** as the next actionable profile families.

Keep autoencoder, TS2Vec, and PatchTST as registered stubs until CPU diagnostics show that simple profiles leave meaningful residual value.

For 4h, favor engineered/regime/PCA.

For 1h, favor engineered/PCA/regime first, then TS2Vec before PatchTST if learned profiles become justified.

**Stage C remains locked throughout.**

---

## 12. Source map

### 12.1 Uploaded project documents used

1. `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
2. `PHASE_3X_UNSUPERVISED_CAUSAL_AUDIT.md`
3. `stage3x_market_state_causal_contract.md`
4. `PROJECT3_MARKET_STATE_REPRESENTATION_AGENT_SPECS_2026_05_23.md`

### 12.2 External technical references

1. scikit-learn PCA documentation: <https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html>
2. scikit-learn IncrementalPCA documentation: <https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.IncrementalPCA.html>
3. scikit-learn MinCovDet documentation: <https://scikit-learn.org/stable/modules/generated/sklearn.covariance.MinCovDet.html>
4. scikit-learn KMeans documentation: <https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html>
5. scikit-learn GaussianMixture documentation: <https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html>
6. TS2Vec paper: <https://arxiv.org/abs/2106.10466>
7. PatchTST paper: <https://arxiv.org/abs/2211.14730>
8. PatchTST official repository: <https://github.com/yuqinie98/PatchTST>
9. hmmlearn repository: <https://github.com/hmmlearn/hmmlearn>
10. statsmodels time-series analysis documentation: <https://www.statsmodels.org/stable/tsa.html>
11. PyPortfolioOpt other optimizers documentation: <https://pyportfolioopt.readthedocs.io/en/latest/OtherOptimizers.html>
12. Riskfolio-Lib documentation: <https://riskfolio-lib.readthedocs.io/>
