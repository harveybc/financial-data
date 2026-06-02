# Phase 3X Unsupervised + Causal Audit Lane — Skeptical Review

**Project:** Project 3 — Financial-data / RL trading research pipeline  
**Target first candidate:** `ETHUSDT 4h + SAC + tech_stat`  
**Strict held-out firewall:** no data, model fitting, tuning, thresholding, prompt context, synthetic generation, or validation access from `2025-01-01` onward before final locked Stage C.  
**Reviewer role:** senior quant ML researcher and skeptical reviewer.  
**Purpose:** define the safest P0 implementation order, leakage traps, validation gates, forbidden actions, and go/no-go checklist for introducing train-only regime/OOD/causal-audit features into the RL pipeline.

---

## 0. Reviewer Verdict

The Phase 3X lane is worth adding, but only as a **controlled audit-and-feature-variant lane**, not as a new optimization loop.

The safest interpretation is:

> Diagnostics first, train-only features second, deterministic overlays third, and only then paired RL comparison.

The most promising P0 value is **regime awareness plus OOD exposure control**, not causal discovery. HMM/GMM/K-means regimes and OOD scores can plausibly reduce fragility for `ETHUSDT 4h + SAC + tech_stat`. The causal/leakage screen is more valuable as a **risk detector** than as an alpha-discovery engine.

The project should treat every added regime count, covariance estimator, KNN value, feature mask, threshold, and overlay rule as a potential overfitting path. Nothing in this lane should touch Stage C until all artifacts and rules are frozen.

---

# 1. Safest P0 Implementation Order

## 1.1 P0.0 — Freeze the Phase 3X Experimental Contract

Before fitting HMM, GMM, K-means, Mahalanobis, KNN, Granger, or any conditional-dependence screen, create a frozen Phase 3X contract.

```text
Target candidate:
  asset: ETHUSDT
  timeframe: 4h
  RL algorithm: SAC
  base feature family: tech_stat

Hard dates:
  heldout_start: 2025-01-01
  no model, scaler, clusterer, test, threshold, prompt, or feature selector may fit on >= 2025-01-01

Allowed P0 outputs:
  diagnostics
  train-only regime features
  train-only OOD scores
  leakage audit reports
  feature redundancy/stability reports

Forbidden P0 outputs:
  direct Stage C changes
  post-2025 feature fitting
  validation-tuned thresholds
  automatic feature deletion
  causal-alpha claims
```

**Rationale:** Phase 3X adds a new search surface. DSR and PBO/CSCV exist because selecting among many backtests, feature variants, and thresholds can produce false discoveries even when every individual backtest appears reasonable.

References:

- Bailey & López de Prado, *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*: <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>
- Bailey et al., *The Probability of Backtest Overfitting*: <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>

---

## 1.2 P0.1 — Build the Deterministic Data and Leakage Contract

Implement this before any ML method.

Required checks:

```text
1. Input feature files are exactly identified and hashed.
2. Fit period, validation period, and held-out period are explicitly stored.
3. All scalers, imputers, covariances, clusterers, encoders, and thresholds are fit on train only.
4. No row >= 2025-01-01 is used in any fitting artifact.
5. Feature computation is causal at each timestamp.
6. Warm-up windows are handled explicitly.
7. No current or future target return enters the regime, OOD, or causal feature set.
8. Bar-action timing is explicitly defined.
```

The existing `tech_stat` table contains primitive OHLCV plus many rolling and derived fields: returns, log returns, moving averages, EMA ratios, MACD, RSI, stochastic oscillator, Williams %R, CCI, ROC, momentum, Bollinger bands, ATR/NATR, historical volatility, OBV, VWAP, MFI, rolling moments, realized variance, autocorrelation, squared-return autocorrelation, volatility-regime flags, Hurst proxy, and z-score features. This is useful, but it increases leakage risk because many columns are rolling-window functions whose causal direction must be verified.

---

## 1.3 P0.2 — Produce Feature Redundancy and Stability Reports Before Regime Fitting

Run redundancy/stability reports before HMM/GMM/K-means because they identify which input dimensions are too collinear, unstable, or redundant.

Recommended output:

```text
feature_redundancy_stability_report.md
feature_redundancy_matrix.parquet
feature_cluster_representatives.yaml
feature_stability_by_train_fold.parquet
```

Minimum tests:

```text
1. Pairwise Spearman and Pearson correlation.
2. Rolling correlation stability.
3. Missingness and warm-up-window profile.
4. Variance and near-constant-column detection.
5. Cross-fold feature rank stability.
6. Feature-family grouping:
   - returns
   - trend
   - volatility
   - volume/liquidity
   - rolling moments
   - existing volatility-regime flags
```

**Reason:** HMM/GMM on a redundant feature matrix can produce unstable regimes driven by duplicated versions of the same signal. Redundancy reduction is not alpha discovery; it is overfit-risk reduction.

---

## 1.4 P0.3 — Fit Simple Regime Baselines in This Order

Use this order:

```text
A. K-means on robust-scaled compact regime feature set
B. GMM on the same compact feature set
C. Gaussian HMM on the same compact feature set
D. Compare all three as diagnostics before exposing them to RL
```

K-means is not state of the art, but it is a useful cheap baseline. GMM provides soft regime probabilities and can be selected with AIC/BIC. HMM adds temporal coherence through state-transition dynamics.

References:

- scikit-learn Gaussian mixture documentation: <https://scikit-learn.org/stable/modules/mixture.html>
- Rabiner, *A Tutorial on Hidden Markov Models and Selected Applications in Speech Recognition*: <https://www.cs.ubc.ca/~murphyk/Bayes/rabiner.pdf>
- Hamilton, *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*: <https://www.jstor.org/stable/1912559>

Use a **compact regime feature set**, not the entire `tech_stat` matrix:

```text
regime_input_features:
  log_return_1
  roll_std_ret_20
  roll_std_ret_60
  roll_skew_ret_60
  roll_kurt_ret_60
  realized_var_12
  realized_var_48
  autocorr_lag1_100
  sqret_autocorr_lag1_100
  atr_14
  natr_14
  volume_ratio_20
  trend_slope_50
  trend_strength_50
```

Do not include future returns, labels, validation metrics, RL actions, reward, PnL, or any feature that is unavailable at the action timestamp.

---

## 1.5 P0.4 — Add OOD Scores After Regime Baselines

Add OOD only after the regime diagnostics are stable enough to interpret.

Recommended order:

```text
A. robust Mahalanobis distance on compact train feature set
B. robust Mahalanobis distance by regime
C. KNN latent distance using train-only learned embeddings
D. regime entropy / low posterior confidence
E. combined OOD score as diagnostics only
```

Robust Mahalanobis is attractive because it is auditable and cheap. KNN/local-density methods are useful for anomaly scoring, but they become dangerous if their reference sets or embeddings were fit across validation or held-out data.

References:

- scikit-learn robust covariance / Mahalanobis example: <https://scikit-learn.org/stable/auto_examples/covariance/plot_mahalanobis_distances.html>
- Breunig et al., *LOF: Identifying Density-Based Local Outliers*: <https://webdocs.cs.ualberta.ca/~zaiane/pub/check/breunig.pdf>

If KNN latent distance uses learned LSTM/CNN embeddings, those embeddings must be refit or verified as train-only for the relevant split. Any embedding trained across validation or held-out time is contaminated for Phase 3X.

---

## 1.6 P0.5 — Run Causal/Leakage Audit Last, Diagnostics Only

Run lag-only Granger or conditional-dependence screening only after the data, regime, and OOD reports exist.

The P0 causal audit should answer:

```text
1. Which features suspiciously predict future returns too well?
2. Which features are redundant after conditioning?
3. Which features appear only because of rolling-window leakage?
4. Which relationships survive train-fold resampling?
5. Which features should be manually audited before RL consumes them?
```

It should **not** automatically remove or promote features.

References:

- Granger, *Investigating Causal Relations by Econometric Models and Cross-spectral Methods*: <https://www.jstor.org/stable/1912791>
- Runge, *Discovering contemporaneous and lagged causal relations in autocorrelated nonlinear time series datasets*: <https://proceedings.mlr.press/v124/runge20a/runge20a.pdf>
- Tigramite documentation: <https://jakobrunge.github.io/tigramite/>

---

# 2. Methods Most Likely to Add Real Validation Value Versus Complexity

## 2.1 Highest-Probability Value

| Method | Likely value | Reason | Skeptical note |
|---|---:|---|---|
| Feature redundancy/stability report | High | Reduces avoidable overfit and collinearity before adding more features. | Not alpha-generating; value is risk reduction. |
| HMM/GMM regime probabilities | Medium/high | Regime state can help SAC condition behavior on volatility, trend, liquidity, and crash/recovery context. | Regime labels can be unstable and arbitrary. |
| Regime entropy | Medium/high | Captures model uncertainty; useful for exposure reduction during ambiguous states. | Entropy threshold can be overfit. |
| Robust Mahalanobis OOD score | Medium | Cheap, auditable, good first OOD baseline. | Gaussian/covariance assumptions are weak in fat-tailed financial data. |
| KNN latent distance | Medium | Can detect unfamiliar patterns in learned embedding space. | Dangerous if embeddings were trained across validation/held-out. |
| Lag-only leakage audit | High as governance | Finds suspicious feature-target relationships. | Low direct alpha value. |

Financial returns exhibit stylized facts such as heavy tails, volatility clustering, weak raw-return autocorrelation, stronger absolute/squared-return autocorrelation, and nonlinear dependence. Any method that ignores these properties can look clean in-sample and fail under realistic validation.

Reference:

- Cont, *Empirical properties of asset returns: stylized facts and statistical issues*: <https://www-stat.wharton.upenn.edu/~steele/Resources/FTSResources/StylizedFacts/Cont2001.pdf>

---

## 2.2 Lower Immediate Value / Higher Risk

| Method | Likely value | Reason to delay |
|---|---:|---|
| Full PCMCI+ feature selection | Medium but risky | Better than pairwise Granger, but easy to turn into hidden feature-search. |
| Automatic causal feature masks | Risky | Can remove useful robust predictors or preserve spurious ones under wrong assumptions. |
| Regime-specific SAC policies | Too early | Multiplies model count, data fragmentation, and selection bias. |
| Complex latent OOD ensemble | Too early | Hard to attribute whether uplift comes from signal or overfitted thresholding. |
| LLM interpretation of causal graph | Diagnostic only | Useful for reporting, not for model promotion. |

Skeptical conclusion: **the methods most likely to help first are simple, auditable, train-only regime/OOD diagnostics, not complex causal selectors.**

---

# 3. Leakage Traps Most Likely in This Lane

## 3.1 Split Leakage Through Unsupervised Fitting

This is the highest-risk trap.

Forbidden examples:

```text
fit scaler on train + validation
fit HMM on all pre-2025 data if validation is inside pre-2025
fit GMM/K-means using validation
fit Mahalanobis covariance using validation
fit KNN reference set using validation
fit learned embeddings using validation
fit thresholds using validation and then report validation uplift
```

Unsupervised does **not** mean leakage-free. Any fitted parameter can leak distributional information.

---

## 3.2 Rolling-Window Leakage

Leakage can occur if:

```text
rolling windows are centered rather than trailing
resampling labels bars by close time but features use future intrabar values
warm-up rows are backfilled
normalization uses full-series mean/std
technical indicators are recomputed with future-filled values
```

Every Phase 3X feature must pass prefix-only recomputation tests.

---

## 3.3 Validation-Tuned OOD Thresholds

Example leakage pattern:

```text
try OOD threshold = 90%, 92.5%, 95%, 97.5%, 99%
choose the one with best validation Sharpe
pretend it was an unsupervised risk rule
```

That is model selection. It must be counted in DSR/PBO accounting, and the threshold must be trained/frozen using train-only inner splits.

---

## 3.4 Regime-Label Hindsight Through HMM Smoothing

HMM smoothing can use future observations to infer the most likely latent state. For live-trading features, use **filtering**, not full-sequence smoothing.

```text
allowed as RL feature:
  p(z_t | x_1, ..., x_t)

forbidden as live RL feature:
  p(z_t | x_1, ..., x_T)
```

Full-sequence Viterbi or posterior smoothing can leak future data into current regime labels.

---

## 3.5 Causal Screen Using Target-Contaminated Variables

Dangerous examples:

```text
current-bar close-derived feature used to predict current-bar reward
future_return_h accidentally included as a candidate parent
return_5 or return_10 not lagged properly
feature computed from a bar whose close is not yet available at action time
```

The RL environment’s action timestamp must be explicit. If the agent acts at the 4h bar close for the next bar, just-closed-bar features may be allowed. If the agent acts at the bar open, they are not.

---

## 3.6 Multiple-Testing Leakage

Each of these is a separate trial:

```text
number of HMM states
covariance type
feature subset
scaler type
KNN k
Mahalanobis estimator
OOD threshold
overlay multiplier
Granger lag depth
conditional-dependence p-value threshold
feature mask
```

Backtest overfitting is not only caused by models. It is caused by searching many specifications and selecting winners.

---

# 4. Required Tests Before RL Consumes Phase 3X Features

## 4.1 Data-Contract Tests

Before RL sees any new feature:

```text
[ ] artifact has config hash
[ ] artifact has git commit hash
[ ] artifact has input file hashes
[ ] artifact has fit_start and fit_end
[ ] artifact declares uses_heldout = false
[ ] artifact declares uses_validation_for_fit = false
[ ] all transforms are fit on train only
[ ] no row >= 2025-01-01 is used in fitting
[ ] feature timestamps align exactly to ETHUSDT 4h environment timestamps
```

---

## 4.2 Causal Recalculation / Prefix Tests

Required:

```text
1. Prefix recomputation test:
   recompute feature at time t using only rows <= t;
   compare with batch artifact.

2. Boundary test:
   verify train/validation boundary does not change train-period features.

3. Fit-period perturbation test:
   remove validation period entirely;
   train-period features must remain unchanged.

4. Bar-action timing test:
   verify features are available at action time.

5. Warm-up test:
   early NaNs are explicit; no backward fill from future values.
```

Pass criterion:

```text
max_abs_difference <= tolerance for deterministic features
no change in train features after removing validation data
no future timestamp dependency detected
```

---

## 4.3 Regime-Feature Tests

Required:

```text
1. Regime count fixed before validation.
2. Regime input feature list fixed before validation.
3. Scaling fit on train only.
4. HMM/GMM/K-means fit on train only.
5. State labels canonicalized by train-period properties:
   e.g., low-vol, mid-vol, high-vol, crash/recovery.
6. Regime stability measured across train subfolds.
7. Filtering-only HMM probabilities used for RL features.
8. Full-sequence smoothed probabilities allowed only for offline diagnostics.
```

Pass criterion:

```text
regime occupancy:
  no regime has trivial occupancy unless explicitly labeled rare/crash

regime interpretability:
  regimes differ materially in volatility, drawdown, volume, or trend

regime stability:
  similar train subfolds produce comparable regime definitions

no hindsight:
  feature generation at t uses only x_<=t
```

---

## 4.4 OOD-Feature Tests

Required:

```text
1. Reference distribution fit on train only.
2. OOD score calibrated on train-only inner folds.
3. Validation used only once for evaluation.
4. OOD score distribution reported by regime.
5. False-alarm rate reported.
6. Correlation with volatility and drawdown reported.
7. Correlation with transaction cost/slippage reported.
8. OOD score not directly using realized future loss.
```

Pass criterion:

```text
OOD score must identify at least some known train-period stress windows.
OOD score must not simply equal volatility under a different name.
OOD score must not mark almost all validation as OOD.
OOD score must not create exposure collapse unless predeclared.
```

---

## 4.5 Causal/Leakage Audit Tests

Required:

```text
1. All candidate causes are lagged.
2. All targets are explicitly future targets.
3. No current/future target leakage.
4. Multiple-testing correction applied.
5. Results stable across train subfolds.
6. Negative controls included.
7. Reverse-time test included.
8. Randomized-target test included.
```

Suggested negative controls:

```text
random_noise_feature
permuted_feature_with_same_distribution
future-shifted feature intentionally injected to verify detector catches leakage
reverse-time Granger screen
```

Pass criterion:

```text
known leakage canary is detected
random controls are not promoted
feature rankings are not wildly unstable across subfolds
causal report is generated as audit evidence, not automatic model mutation
```

---

## 4.6 Downstream RL Readiness Tests

Before RL consumes features:

```text
[ ] feature artifact passes all data-contract tests
[ ] no validation/held-out fitting
[ ] no Stage C dependency
[ ] observation dimensions are deterministic and documented
[ ] feature values finite after warm-up
[ ] missingness mask is explicit
[ ] baseline SAC + tech_stat run is reproducible
[ ] new variant differs only by declared Phase 3X features or overlay
[ ] same seeds, same cost model, same episode definitions
```

---

# 5. What Should Be Forbidden

## 5.1 Absolute Prohibitions

```text
1. Any fit, tune, threshold calibration, embedding training, clustering, or prompt context on data >= 2025-01-01.
2. Any Stage C access before final locked evaluation.
3. Any HMM full-sequence smoothing feature used as live RL input.
4. Any validation-tuned OOD threshold presented as train-only.
5. Any causal graph treated as proof of tradable causality.
6. Any automatic feature removal without a paired registered RL test.
7. Any regime-specific policy training in P0.
8. Any threshold/model-count search not logged as a trial.
9. Any use of synthetic, stress, or OOD performance as real trading evidence.
10. Any change to SAC hyperparameters inside the Phase 3X comparison.
```

---

## 5.2 Additional P0 Prohibitions

```text
1. Deep contrastive encoders unless embeddings are refit train-only.
2. PCMCI+ as feature selector before the leakage framework is validated.
3. Multi-agent LLM interpretation inside the promotion decision.
4. Hand-renaming regimes after seeing validation performance.
5. Choosing “good” regimes based on validation PnL.
6. Dropping bad validation windows as OOD and then claiming improved performance.
```

The last item is especially important. OOD exposure reduction can become a disguised way to remove losing periods. It must be evaluated against opportunity cost: missed winners, lower exposure, reduced return opportunity, and risk-adjusted improvement.

---

# 6. Should HMM/GMM Regimes Be Features, Overlays, or Diagnostics?

## 6.1 Recommended Sequence

```text
Step 1: diagnostics only
Step 2: observation features
Step 3: deterministic risk overlay
Step 4: never P0 regime-specific RL policies
```

---

## 6.2 Diagnostics Only — Mandatory First

Use regimes first to answer:

```text
Does ETHUSDT 4h validation behavior differ by regime?
Does the current SAC + tech_stat signal fail in specific regimes?
Does drawdown cluster in high-vol or high-entropy states?
Does turnover increase in ambiguous regimes?
```

This is low-risk and immediately useful.

---

## 6.3 As Features — Allowed After Diagnostics Pass

Preferred regime features:

```text
regime_prob_low_vol
regime_prob_mid_vol
regime_prob_high_vol
regime_entropy
regime_transition_probability
regime_expected_volatility
```

Avoid raw arbitrary labels if possible. Probabilities are better than hard IDs because HMM/GMM label ordering is arbitrary and regime boundaries are uncertain.

---

## 6.4 As Overlays — Allowed Only as a Separate Paired Test

A deterministic overlay might be:

```text
if regime_entropy > train_calibrated_threshold:
    position_multiplier = 0.5

if high_vol_crash_regime_prob > train_calibrated_threshold:
    position_multiplier = 0.5 or 0.0
```

But this must be compared separately against:

```text
A. SAC + tech_stat
B. SAC + tech_stat + regime features
C. SAC + tech_stat + deterministic regime overlay
D. SAC + tech_stat + regime features + overlay
```

---

## 6.5 Regime-Specific Policies — No for P0

Do not train separate SAC policies by regime in P0. That multiplies model count, data fragmentation, and selection bias. It is a P2 idea at best.

---

# 7. How OOD Exposure Reduction Should Be Evaluated

## 7.1 Compare Three or Four Arms, Not Two

Minimum comparison:

```text
A. Baseline:
   SAC + tech_stat

B. Feature-only:
   SAC + tech_stat + OOD scores in observation

C. Overlay-only:
   SAC + tech_stat, but deterministic OOD exposure reducer

D. Feature + overlay:
   SAC + tech_stat + OOD features + deterministic OOD exposure reducer
```

The overlay must be judged against both the raw baseline and the feature-only version.

---

## 7.2 Thresholds Must Be Train-Calibrated

Allowed threshold calibration:

```text
train inner split only:
  threshold = 95th percentile of train OOD score
  or threshold chosen by train-only risk objective

then frozen:
  validation only evaluates
```

Forbidden:

```text
choose threshold that maximizes validation Sharpe
choose threshold that avoids known validation crash
change threshold after seeing validation drawdown
```

---

## 7.3 Required Metrics for OOD Overlay

Report all of the following.

Performance:

```text
net return after costs
Sharpe / Sortino / Calmar
DSR
max drawdown
drawdown duration
```

Risk:

```text
downside deviation
worst 1%, 5% episode returns
volatility by regime
liquidation-like tail episodes if relevant
```

Trading mechanics:

```text
turnover
cost paid
slippage sensitivity
average exposure
number of exposure reductions
number of full vetoes
```

Opportunity cost:

```text
missed positive-return trades
missed high-confidence SAC trades
reduced exposure during profitable regimes
average PnL when OOD flag active
```

Robustness:

```text
seed variance
paired bootstrap confidence interval
performance under cost stress
performance under slippage stress
```

OOD reduction is successful only if it improves **risk-adjusted validation performance after costs** without merely hiding from the market.

---

## 7.4 Required Failure Analysis

For every OOD overlay run, produce:

```text
ood_overlay_failure_cases.md

Sections:
  1. largest losses not prevented
  2. largest winners incorrectly reduced
  3. regimes where OOD was overactive
  4. regimes where OOD was inactive during drawdown
  5. turnover/cost impact
  6. whether the overlay is just volatility targeting
```

This is necessary because an OOD overlay can look good by reducing exposure everywhere. That is not intelligence; it is leverage reduction.

---

# 8. Go/No-Go Checklist for the First ETHUSDT 4h Paired Variant

## 8.1 Candidate Definition

First variant should be conservative:

```text
Baseline:
  ETHUSDT 4h + SAC + tech_stat

Variant 1:
  ETHUSDT 4h + SAC + tech_stat + regime probabilities + regime entropy

Variant 2:
  ETHUSDT 4h + SAC + tech_stat + OOD score

Variant 3:
  ETHUSDT 4h + SAC + tech_stat + regime probabilities + regime entropy + OOD score
```

Do not include in the first paired test:

```text
causal feature mask
regime-specific policy
validation-tuned overlay
PCMCI+ selector
```

Reason: HMM/GMM/OOD has plausible robustness value; causal masks introduce more researcher degrees of freedom.

---

## 8.2 Pre-RL Go Checklist

Proceed to RL only if all are true:

```text
[ ] split contract is frozen and logged
[ ] no artifact uses data >= 2025-01-01
[ ] no artifact uses validation for fitting
[ ] train/validation/Stage C boundaries are explicit
[ ] feature input list is frozen
[ ] scaler/imputer artifacts are train-only
[ ] HMM/GMM/K-means artifacts are train-only
[ ] OOD reference distribution is train-only
[ ] regime features use causal filtering, not future smoothing
[ ] feature files are timestamp-aligned to ETHUSDT 4h
[ ] no non-finite values after warm-up
[ ] warm-up rows are masked or dropped consistently
[ ] feature dimensionality is documented
[ ] random seeds are fixed
[ ] baseline SAC run is reproducible
```

---

## 8.3 Regime Go Checklist

```text
[ ] at least two regimes have meaningful occupancy
[ ] regimes differ in volatility/trend/drawdown/volume properties
[ ] regime definitions are stable across train subfolds
[ ] regime labels are canonicalized by train-period statistics
[ ] regime entropy is finite and interpretable
[ ] validation regime distribution is reported but not used for refitting
[ ] full-sequence smoothed labels are not used as live features
```

No-go if:

```text
[ ] one regime dominates almost all samples
[ ] regimes are indistinguishable from simple volatility quantiles
[ ] regime assignments change wildly across train subfolds
[ ] regime features require future observations
```

---

## 8.4 OOD Go Checklist

```text
[ ] OOD score is calibrated on train only
[ ] OOD score is not just duplicate volatility
[ ] OOD score identifies known stress windows in train
[ ] false-alarm rate is reported
[ ] OOD distribution by regime is reported
[ ] threshold, if any, is frozen before validation
[ ] overlay rule, if any, is frozen before validation
[ ] OOD feature has no dependence on future return/PnL
```

No-go if:

```text
[ ] OOD score flags almost everything
[ ] OOD score flags almost nothing
[ ] threshold is chosen after validation inspection
[ ] overlay mostly reduces exposure without improving risk-adjusted return
```

---

## 8.5 Causal/Leakage Audit Go Checklist

For P0, this is a **gate**, not a trading-feature source.

```text
[ ] all candidate predictors are lagged
[ ] all targets are future targets
[ ] leakage canary test is detected
[ ] randomized controls are not selected
[ ] reverse-time screen does not produce stronger evidence than forward-time screen
[ ] suspicious features are reported for manual audit
[ ] no automatic feature deletion occurs
```

No-go if:

```text
[ ] leakage canary is not detected
[ ] random controls appear predictive
[ ] current/future target leakage is found
[ ] causal screen results are used to tune validation performance
```

---

## 8.6 RL Paired-Test Go Checklist

Run the first paired test only if:

```text
[ ] same SAC config as baseline
[ ] same train/validation windows
[ ] same seeds
[ ] same cost model
[ ] same slippage model
[ ] same reward definition
[ ] same episode boundaries
[ ] same evaluation script
[ ] Phase 3X variant count is logged for multiple-testing correction
```

Suggested minimum seeds:

```text
at least 5 seeds for P0 smoke comparison
prefer 10+ seeds before promotion discussion
```

Cost scenarios:

```text
base cost
moderate cost stress
high slippage stress
```

Go if:

```text
[ ] validation net performance improves after costs
[ ] DSR improves or remains acceptable
[ ] max drawdown improves or does not materially worsen
[ ] turnover does not materially increase
[ ] seed variance decreases or does not worsen
[ ] cost/slippage stress does not erase the advantage
[ ] improvement is paired, not cherry-picked
[ ] feature/overlay artifact is frozen before any Stage C consideration
```

No-go if:

```text
[ ] uplift appears only in one seed
[ ] uplift appears only before costs
[ ] turnover explodes
[ ] drawdown worsens materially
[ ] overlay simply reduces exposure everywhere
[ ] variant only wins after validation-tuned thresholds
[ ] causal audit finds unresolved leakage
```

---

# 9. Final Recommended P0 Sequence

Use this exact order:

```text
1. Freeze Phase 3X split/config/artifact contract.
2. Build leakage/data-contract tests.
3. Produce feature redundancy/stability report.
4. Fit K-means/GMM/HMM regime diagnostics train-only.
5. Validate causal filtering for regime probabilities.
6. Fit robust Mahalanobis and KNN-latent OOD diagnostics train-only.
7. Run lag-only causal/leakage audit as diagnostics only.
8. Only then create RL-consumable feature variants.
9. Run paired ETHUSDT 4h + SAC + tech_stat comparisons.
10. Decide go/no-go using real validation only.
```

---

# 10. Final Prioritization

Most likely to help:

```text
1. regime probabilities
2. regime entropy
3. robust OOD score
4. feature redundancy/stability report
5. causal/leakage audit as gate
```

Lower immediate value:

```text
1. causal feature masks
2. regime-specific policies
3. complex PCMCI+ selection
4. OOD ensembles
```

---

# 11. Skeptical Bottom Line

Phase 3X is a good idea if it is treated as a **robustness and leakage-control lane**. It is a bad idea if it becomes a hidden second optimizer.

For the first `ETHUSDT 4h + SAC + tech_stat` paired variant, the cleanest comparison is:

```text
SAC + tech_stat
vs
SAC + tech_stat + train-only HMM/GMM regime probabilities + regime entropy
vs
SAC + tech_stat + train-only robust OOD score
vs
SAC + tech_stat + regime probabilities + OOD score
```

Keep causal screening as an audit gate until it proves it catches leakage without destabilizing the experiment.

---

# 12. Reference Index

1. Bailey, D. H., & López de Prado, M. *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*. <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>
2. Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. *The Probability of Backtest Overfitting*. <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>
3. Cont, R. *Empirical properties of asset returns: stylized facts and statistical issues*. <https://www-stat.wharton.upenn.edu/~steele/Resources/FTSResources/StylizedFacts/Cont2001.pdf>
4. Rabiner, L. R. *A Tutorial on Hidden Markov Models and Selected Applications in Speech Recognition*. <https://www.cs.ubc.ca/~murphyk/Bayes/rabiner.pdf>
5. Hamilton, J. D. *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*. <https://www.jstor.org/stable/1912559>
6. scikit-learn Gaussian Mixture Models documentation. <https://scikit-learn.org/stable/modules/mixture.html>
7. scikit-learn robust covariance / Mahalanobis example. <https://scikit-learn.org/stable/auto_examples/covariance/plot_mahalanobis_distances.html>
8. Breunig, M. M., Kriegel, H.-P., Ng, R. T., & Sander, J. *LOF: Identifying Density-Based Local Outliers*. <https://webdocs.cs.ualberta.ca/~zaiane/pub/check/breunig.pdf>
9. Granger, C. W. J. *Investigating Causal Relations by Econometric Models and Cross-spectral Methods*. <https://www.jstor.org/stable/1912791>
10. Runge, J. *Discovering contemporaneous and lagged causal relations in autocorrelated nonlinear time series datasets*. <https://proceedings.mlr.press/v124/runge20a/runge20a.pdf>
11. Tigramite documentation. <https://jakobrunge.github.io/tigramite/>
