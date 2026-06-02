# Project 3 Phase 4 Research Memo — Synthetic Data Augmentation for RL Trading

**Prepared for:** Project 3 orchestrator / agent-multi integration lane  
**Scope:** Crypto and FX RL trading pipeline, fixed PPO/SAC/DQN, Stage C held-out firewall from `2025-01-01` onward  
**Current signal context provided by user:** best current Stage A signal is `ETHUSDT 4h`, SAC actor-critic, `tech_stat` features  
**Primary objective:** determine whether synthetic data can improve *real out-of-sample trading robustness under realistic costs*, not whether synthetic OHLCV looks visually plausible.

---

## 0. Non-negotiable project constraints

Project 3 is explicitly data/feature-centric: PPO, SAC, and DQN configurations remain fixed while the experiment varies asset, timeframe, feature input set, and feature-engineering technique. Synthetic data must therefore be treated as an additional *training-data intervention*, not as a new algorithm search or a post-hoc rescue path.

The project already has a strict Stage A/B/C structure:

- Stage A: broad, low-budget screening.
- Stage B: full-budget validation of top configurations.
- Stage C: one deterministic held-out rollout on `2025-01-01` onward per validated candidate.

The synthetic-data lane must not weaken this discipline. Synthetic data must never be trained on, tuned on, generated from, validated against for promotion, or prompt-contextualized by Stage C data.

---

## 1. Executive recommendation

### 1.1 Should synthetic data augmentation be included?

**Yes, but only as a controlled Phase 4 training-augmentation lane after Stage B has identified strong candidate asset/timeframe/feature/model combinations.**

Synthetic data is potentially valuable for this project because RL policies are sample-hungry, sensitive to regime imbalance, and prone to memorizing historical path quirks. However, synthetic data also adds another search dimension and can easily create fake alpha if it is allowed to influence candidate selection informally.

The correct framing is:

> Synthetic data is not evidence of tradability. Synthetic data is an intervention that may improve the robustness of policies that are still evaluated only on real, untouched data.

### 1.2 Phase 4 after Stage B, or earlier exploratory branch?

Use both, but with different permissions.

#### Allowed before Stage B: infrastructure-only exploratory branch

An exploratory branch may be started earlier to build:

- primitive OHLCV schema separation;
- generator interfaces;
- stationary/block bootstrap baseline;
- regime-conditioned bootstrap baseline;
- synthetic-data validation reports;
- artifact registry and deterministic manifests.

This branch must not:

- promote RL candidates;
- change Stage A or Stage B rankings;
- tune Stage A/B based on synthetic performance;
- access Stage C data;
- add new RL model families.

#### Main scientific use: Phase 4 after Stage B

Phase 4 should run only on candidates that passed Stage B real-data validation. For example, if `ETHUSDT 4h + SAC + tech_stat` survives Stage B gates, it becomes a valid Phase 4 candidate.

### 1.3 What must be forbidden?

Synthetic data should be rejected or quarantined if any of the following occurs:

1. **Stage C contamination:** any use of data at or after `2025-01-01` for generator fitting, tuning, threshold selection, prompt context, feature normalization, regime labeling, or nearest-neighbor comparison.
2. **Direct generation of deterministic derived indicators:** do not generate `return_1`, `log_return_1`, `sma_*`, `ema_*`, `macd`, `rsi_*`, Bollinger bands, ATR, OBV, VWAP, rolling skew/kurtosis, realized variance, regime flags, or z-scores directly. Generate primitive market paths and recompute features causally.
3. **Synthetic validation as evidence:** never treat performance on synthetic validation episodes as evidence of trading edge.
4. **Post-hoc generator fishing:** do not try many generator families, prompts, seeds, window sizes, or blending ratios and report only winners without including them in DSR/PBO accounting.
5. **Validation leakage through preprocessing:** scalers, PCA/autoencoder encoders, volatility normalizers, HMM labels, and regime thresholds must be fit only on the allowed training window for each experiment.
6. **Stage C reruns:** no synthetic intervention may cause a second held-out run after seeing Stage C results.
7. **All-column generation:** never train a generic tabular generator on the full feature matrix as the main method; it will generate internally inconsistent indicator relationships.
8. **Changing the current RL hypothesis midstream:** Phase 4 may augment training for Stage B winners; it must not retroactively redefine what Stage A/B were testing.

---

## 2. Data representation recommendation

The uploaded example table contains primitive market fields and many deterministic or semi-deterministic feature columns: `OPEN`, `HIGH`, `LOW`, `CLOSE`, `VOLUME`, `typical_price`, returns, log returns, SMA/EMA ratios, MACD, RSI, stochastic oscillator, Williams %R, CCI, ROC, momentum, Bollinger bands, ATR/NATR, historical volatility, EMA crosses, OBV, volume ratios, VWAP, MFI, rolling moments, realized variance, autocorrelation, volatility-regime flags, Hurst proxy, and z-score features.

The generator should therefore operate on **primitive transformed OHLCV**, not on the full feature table.

### 2.1 Generate these primitive transformed variables

For each bar `t`:

```text
r_close_t = log(CLOSE_t / CLOSE_{t-1})
r_open_t  = log(OPEN_t  / CLOSE_{t-1})
d_high_t  = log(HIGH_t / max(OPEN_t, CLOSE_t))        with d_high_t >= 0
d_low_t   = log(min(OPEN_t, CLOSE_t) / LOW_t)         with d_low_t >= 0
v_t       = log1p(VOLUME_t)
```

Then reconstruct:

```text
OPEN_t   = CLOSE_{t-1} * exp(r_open_t)
CLOSE_t  = CLOSE_{t-1} * exp(r_close_t)
HIGH_t   = max(OPEN_t, CLOSE_t) * exp(softplus(x_high_t))
LOW_t    = min(OPEN_t, CLOSE_t) * exp(-softplus(x_low_t))
VOLUME_t = exp(v_t) - 1
```

This makes OHLCV validity enforceable by construction.

### 2.2 Recompute all derived features

After synthetic OHLCV is reconstructed:

1. aggregate from 5m to 15m/1h/4h when multi-timeframe consistency is required;
2. recompute technical/statistical features using the existing feature engine;
3. recompute signal decomposition features only if explicitly needed and documented;
4. recompute learned embeddings using encoders trained only on permitted pre-Stage-C data;
5. write metadata that proves all transforms were fit on allowed windows only.

---

## 3. Methods comparison table

**Score scale:** `1 = low / weak / easy`, `5 = high / strong / difficult`. For risk columns, higher means worse risk.

| Method | Expected value for RL trading | Implementation effort | Leakage risk | Mode-collapse / overfit risk | Stylized-fact preservation | ETHUSDT 4h suitability | 15m crypto/perp suitability | FX suitability | Recommended role |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Stationary / moving-block bootstrap | 3 | 1 | 2 | 1 | 3 | 4 | 3 | 4 | Mandatory P0 baseline |
| Regime-conditioned bootstrap | 4 | 2 | 2 | 2 | 4 | 4 | 4 | 4 | Best first practical augmenter |
| Walk-forward residual bootstrap | 4 | 3 | 2 | 2 | 4 | 5 | 3 | 4 | Strong for ETHUSDT 4h and FX |
| HMM / regime-switching generator | 4 | 3 | 2 | 2 | 4 | 5 | 3 | 4 | P1, especially for 4h regimes |
| GARCH / EGARCH / regime-GARCH | 3 | 2 | 2 | 1 | 4 for volatility, 2 for path structure | 4 | 3 | 4 | Econometric baseline / residual generator |
| VAE / state-space / TimeVAE | 4 | 3 | 2 | 2 | 3–4 | 4 | 3 | 4 | First deep model candidate |
| TimeGAN-style methods | 2–3 | 4 | 3 | 4 | 2–3 | 2 | 3 | 2 | Benchmark only, not first choice |
| COT-GAN / optimal transport GANs | 3 | 4 | 3 | 3 | 4 | 3 | 3 | 3 | Research candidate after P1 |
| Sig-Wasserstein GAN | 4 | 4 | 3 | 3 | 4–5 | 4 | 3 | 4 | Strong path-distribution candidate |
| Diffusion / score-based generators | 4–5 | 5 | 3 | 2 | 4–5 | 4 | 4 | 4 | P2 advanced lane |
| FTS-Diffusion-style financial generator | 4 | 5 | 3 | 3 | 5 | 4 | 3 | 4 | P2 if compute allows |
| Diffusion-TS / general time-series diffusion | 4 | 5 | 3 | 2 | 4 | 4 | 4 | 4 | P2 general deep baseline |
| CoFinDiff / controllable financial diffusion | 5 | 5 | 3–4 | 2–3 | 5 | 4 | 4 | 4 | P2 / P3, only after validation suite is mature |
| TimeVQVAE / vector-quantized generation | 3 | 4 | 3 | 2–3 | 3–4 | 3 | 3 | 3 | Watchlist, not first implementation |
| Synthetic order-flow / microstructure simulation | 1 for 4h, 4 for 15m | 5 | 3 | 3 | 4 if calibrated | 1 | 4–5 | 2 unless FX LOB data exists | 15m/perp stress lane only |
| Full tabular generator over all columns | 1 | 2 | 4 | 4 | 1 | 1 | 1 | 1 | Explicitly forbid as main method |

### 3.1 Method-specific assessment

#### 3.1.1 Stationary / block bootstrap

Politis and Romano’s stationary bootstrap was designed for weakly dependent stationary observations and is appropriate as a minimum time-series resampling baseline. It is cheap, auditable, and hard to beat honestly. Its weakness is that it recombines observed blocks rather than creating new structural regimes.

**Project recommendation:** mandatory P0 baseline. If a deep generator cannot beat this in downstream real-validation utility, the deep generator should be killed.

#### 3.1.2 Regime-conditioned bootstrap

A regime-conditioned bootstrap first labels bars or windows by volatility/trend/crash/liquidity regime, then resamples blocks within regimes or builds regime transition chains. This preserves more of the empirical path structure than unconditional block bootstrap and directly addresses rare-regime imbalance.

**Project recommendation:** highest value / lowest risk first augmenter.

#### 3.1.3 Walk-forward residual bootstrap

Fit a simple causal model on an expanding or rolling window, bootstrap residual blocks, then reconstruct paths. This allows local trend/volatility structure to be preserved while perturbing innovations.

**Project recommendation:** strong for `ETHUSDT 4h`, because 4h data has fewer observations than 5m/15m and benefits from residual perturbation without inventing unrealistic microstructure.

#### 3.1.4 GARCH / regime-GARCH

GARCH directly models conditional heteroskedasticity and volatility clustering. Student-t or skewed-t innovations should be preferred over Gaussian innovations for crypto/FX. GARCH should not be expected to learn full path structure, but it is a useful volatility and residual baseline.

#### 3.1.5 HMM / regime-switching generators

Hamilton-style regime switching provides a tractable way to model latent market states. For this project, HMM labels are useful both as generator conditioning variables and as evaluation strata.

**Project recommendation:** include as P1 if the bootstrap lane shows that regime balancing improves policy robustness.

#### 3.1.6 TimeGAN-style methods

TimeGAN combines adversarial training with a supervised temporal loss. It is a standard reference baseline for synthetic time series. The concern is that GANs can underproduce tails, collapse modes, or memorize local sequences unless aggressively validated.

**Project recommendation:** benchmark only; do not lead with TimeGAN.

#### 3.1.7 COT-GAN and Sig-Wasserstein GAN

COT-GAN uses causal optimal transport to impose temporal causality in the loss. Sig-Wasserstein GAN uses path-signature metrics and has direct relevance to financial path distributions.

**Project recommendation:** these are defensible research candidates after the P0/P1 validation machinery exists. They are not the first implementation because they require more mathematical and engineering care.

#### 3.1.8 VAE / state-space / TimeVAE

TimeVAE and conditional VAE/state-space models are attractive because they are generally easier to train and audit than GANs. They can incorporate trend/seasonality priors and regime conditions.

**Project recommendation:** first deep model after bootstraps and econometric baselines.

#### 3.1.9 Diffusion / score-based generators

Diffusion methods are the most attractive futuristic direction. TimeGrad and CSDI established important diffusion/score-based time-series machinery. Diffusion-TS, FTS-Diffusion, financial diffusion papers, and CoFinDiff make diffusion particularly relevant for synthetic financial paths.

**Project recommendation:** P2 only. Do not start here. Diffusion should be introduced only after the validation suite, artifact registry, and simpler baselines are already working.

#### 3.1.10 Synthetic order-flow / microstructure simulation

ABIDES and JAX-LOB show that high-fidelity and GPU-accelerated market simulation is possible. However, this project’s strongest current candidate is `ETHUSDT 4h`, where order-flow simulation is unlikely to be the highest-value first step. Microstructure simulation is more relevant for 5m/15m crypto/perp experiments, especially if order-book, spread, and funding/liquidation features become important.

**Project recommendation:** defer to a 15m/perp stress-testing lane. Do not use it for the initial ETHUSDT 4h Phase 4 experiment.

---

## 4. Validation protocol before synthetic data can train RL

Synthetic data must pass three gates: **mechanical validity**, **distributional plausibility**, and **downstream real-data utility**.

### 4.1 Mechanical and algebraic validity

Required checks:

```text
CLOSE > 0
OPEN > 0
HIGH >= max(OPEN, CLOSE)
LOW <= min(OPEN, CLOSE)
VOLUME >= 0
timestamp order is strictly increasing
no duplicate timestamps per asset/timeframe
no NaN outside expected warm-up windows
no infinite values
```

After feature recomputation:

```text
typical_price == (HIGH + LOW + CLOSE) / 3
return_1 == CLOSE_t / CLOSE_{t-1} - 1
log_return_1 == log(CLOSE_t / CLOSE_{t-1})
rolling indicators match their causal windows
no feature uses post-bar values
```

### 4.2 Return distribution and stylized facts

Required metrics, measured against real training and untouched real validation distributions:

- mean, standard deviation, skewness, kurtosis;
- quantiles: 0.1%, 1%, 5%, 50%, 95%, 99%, 99.9%;
- tail index / Hill estimator where sample size permits;
- Jarque-Bera or equivalent normality diagnostics;
- empirical VaR / expected shortfall comparison;
- distributional distances: KS, Wasserstein, MMD.

Synthetic data should reproduce the important stylized facts described by Cont: heavy tails, weak raw-return autocorrelation, volatility clustering, and stronger absolute/squared-return dependence.

### 4.3 Volatility clustering

Required metrics:

```text
ACF(abs(return), lags=[1,2,5,10,20,50,100])
ACF(return^2,   lags=[1,2,5,10,20,50,100])
realized variance distribution
rolling volatility distribution
volatility-regime transition matrix
```

Kill condition:

```text
Synthetic data fails if it matches marginal return distribution but destroys squared-return autocorrelation or regime persistence.
```

### 4.4 Autocorrelation and cross-correlation

Required metrics:

```text
ACF(return) by lag
ACF(abs(return)) by lag
ACF(squared return) by lag
cross-asset correlation matrix when multi-asset generation is used
rolling correlation distribution
lead/lag correlation checks if cross-source features are included
```

For `ETHUSDT 4h`, single-asset generation can be acceptable in the first Phase 4 iteration. For 15m/perp and cross-source feature sets, multi-asset correlation preservation becomes more important.

### 4.5 Drawdown and path-shape distribution

Required metrics:

```text
max drawdown distribution per synthetic episode
time-under-water distribution
drawdown duration distribution
run-length distribution of positive/negative returns
trend segment duration
crash/recovery segment frequency
```

Kill condition:

```text
Synthetic data fails if it produces plausible one-bar returns but unrealistic episode-level drawdown geometry.
```

### 4.6 Regime coverage

Required metrics:

```text
volatility regime counts
trend/range/crash/recovery regime counts
regime transition matrix
rare-regime oversampling ratio
synthetic-vs-real regime dwell-time distribution
```

Regime balancing is useful only if validation proves that generated rare regimes are plausible, not just more numerous.

### 4.7 Feature correlation preservation

Because Project 3 uses technical/statistical/decomposition/learned features, validation must compare the recomputed synthetic feature matrix to real feature matrices:

```text
Pearson/Spearman correlation matrix distance
feature-family covariance distance
PCA eigenvalue spectrum distance
feature missingness/warm-up mask comparison
mutual information proxy where stable
```

Do not validate only OHLCV if RL consumes `tech_stat` or richer feature sets.

### 4.8 Train/synthetic/validation separation

For every synthetic artifact, log:

```text
real data used for generator fitting
real data excluded from generator fitting
scalers fit period
regime-label fit period
feature-engineering fit period
generated sample count
random seeds
generator hyperparameters
hashes of input and output parquet files
```

Generator fitting must use only allowed training data. Real validation data may be used for one pre-registered evaluation of synthetic usefulness, but not for iterative generator/prompt/hyperparameter tuning unless that tuning is explicitly counted as another trial.

### 4.9 Nearest-neighbor memorization and privacy/leakage checks

Even though financial OHLCV is not usually private in the same way as medical data, memorization is still a scientific leakage risk.

Required checks:

```text
nearest real train window distance for every synthetic window
nearest real validation window distance for every synthetic window
nearest Stage C window distance must not be computed using Stage C data before final held-out authorization
longest exact copied subsequence
rolling-window duplicate count
Distance to Closest Record (DCR)
Nearest Neighbor Distance Ratio (NNDR)
real-vs-synthetic classifier AUC
```

Kill condition:

```text
Synthetic generator fails if synthetic windows are near-duplicates of long training windows, or if they are closer to validation windows than expected under the train-only distribution.
```

### 4.10 Downstream RL paired uplift test

Synthetic data may train RL only after passing the above validation. Final utility is tested with paired RL experiments on real validation data:

```text
A0: real-only RL baseline
A1: real + stationary bootstrap
A2: real + regime bootstrap
A3: real + walk-forward residual bootstrap
A4: real + HMM/GARCH or TimeVAE
A5: real + advanced deep generator, only if P1 succeeds
```

All arms must use:

- same asset/timeframe/feature preset;
- same PPO/SAC/DQN config;
- same seeds;
- same environment logic;
- same cost/slippage scenarios;
- same validation period;
- same run-ledger requirements.

Promotion requires improvement over both real-only and deterministic/bootstrap synthetic baselines.

---

## 5. RL integration design

### 5.1 Primary recommended use: pretraining only

Safest initial integration:

```text
Step 1: pretrain policy on synthetic training episodes
Step 2: fine-tune policy on real training episodes only
Step 3: validate on real validation data only
Step 4: compare against real-only baseline with paired seeds
```

Rationale:

- reduces risk that synthetic artifacts dominate final policy;
- allows synthetic data to shape broad robustness before real data calibrates final behavior;
- cleanly separates generator utility from final real-data performance.

### 5.2 Secondary use: mixed real/synthetic curriculum

Allowed after pretraining-only passes:

```text
warmup phase:      70% synthetic, 30% real
middle phase:      40% synthetic, 60% real
final phase:       0% synthetic, 100% real
```

Alternatively, use a conservative fixed ratio:

```text
p_real >= 0.70
p_synthetic <= 0.30
```

Synthetic data must not dominate the final training distribution.

### 5.3 Regime balancing

Use synthetic data to increase exposure to rare regimes:

- high-volatility downtrends;
- sharp liquidation cascades;
- post-crash recovery;
- low-liquidity chop;
- high funding / basis stress;
- FX macro-event volatility if event-time labels exist.

But regime balancing must be controlled:

```text
maximum rare-regime oversampling ratio = 2x to 4x initially
no promotion unless validation drawdown and cost robustness improve
```

### 5.4 Stress augmentation

Use synthetic data to stress policies under plausible but adverse conditions:

- higher slippage;
- widened spreads;
- delayed execution;
- volatility shocks;
- overnight/weekend crypto gaps;
- funding-rate shocks for perp data;
- exchange outage or missing-bar masks.

Stress augmentation is especially useful even if synthetic data does not improve average validation return, because it can expose fragile policies.

### 5.5 Adversarial market scenarios

Allowed only as a robustness test, not as a source of performance evidence.

Examples:

```text
adversarial volatility spike around existing support/resistance
synthetic whipsaw paths after strong trend signal
cost shock during high-turnover policy regime
volume collapse during large position exposure
```

### 5.6 Should synthetic data be used for evaluation?

**No. Synthetic data must not be used as final evaluation evidence.**

Synthetic evaluation can be used for debugging and stress characterization, but not for promotion claims. The only meaningful trading-performance evidence is real validation and final Stage C held-out performance. Synthetic data is generated from the historical training distribution, so it is not an independent market sample.

---

## 6. Phase 4 experimental plan

### 6.1 Candidate selection from Stage B

A candidate enters Phase 4 only if it satisfies all of the following on real Stage B validation:

```text
candidate is in top N = 3 to 5 by cost-adjusted validation score
DSR is positive and materially better than simple baselines
PBO/CSCV does not indicate severe selection overfit where feasible
max drawdown is within pre-registered tolerance
performance survives conservative cost/slippage scenario
seed dispersion is acceptable
turnover is not pathological
feature/source ablation does not show one fragile column causing all performance
```

The current `ETHUSDT 4h + SAC + tech_stat` signal should be the first Phase 4 candidate only if it passes these Stage B criteria.

### 6.2 Generator training split

Do not change the Stage A/B/C definitions. Within the pre-2025 data, use the existing project split discipline. If the existing Stage B split is already fixed, respect it exactly.

Recommended abstract split:

```text
real_train_for_generator:
  subset of pre-2025 data already allowed for model training

generator_internal_dev:
  optional subset inside training period only, used for generator diagnostics

real_rl_train:
  same real training window used by Stage B candidate

real_rl_validation:
  same real validation window used by Stage B candidate

stage_c_held_out:
  2025-01-01 onward, forbidden until final one-time evaluation
```

No scaler, HMM, volatility threshold, VAE encoder, diffusion model, bootstrap block selection, or prompt may be fit using Stage C data.

### 6.3 Generated dataset versions

Create immutable dataset versions:

```text
synth_v0_stationary_bootstrap
synth_v1_regime_bootstrap
synth_v2_walk_forward_residual_bootstrap
synth_v3_hmm_garch
synth_v4_timevae_cvae
synth_v5_sigwgan_or_cotgan_optional
synth_v6_diffusion_optional
```

Each version must include:

```text
manifest.json
input_hashes.json
generator_config.yaml
fit_report.md
validation_report.md
synthetic_ohlcv.parquet
recomputed_features.parquet
nearest_neighbor_report.json
stylized_facts_report.json
```

### 6.4 Paired baseline comparisons

For each Phase 4 candidate, run:

```text
B0: real-only Stage B reproduction
B1: synthetic pretrain + real fine-tune, stationary bootstrap
B2: synthetic pretrain + real fine-tune, regime bootstrap
B3: synthetic pretrain + real fine-tune, walk-forward residual bootstrap
B4: mixed curriculum, best P0/P1 generator only
B5: stress augmentation, best P0/P1 generator only
```

Optional deep arms only after P0/P1 demonstrate value:

```text
B6: TimeVAE/CVAE pretrain + real fine-tune
B7: SigWGAN/COT-GAN pretrain + real fine-tune
B8: diffusion/CoFinDiff pretrain + real fine-tune
```

### 6.5 Required seeds

Minimum:

```text
RL seeds:        101, 202, 303, 404, 505
generator seeds: 11, 22, 33 for stochastic/deep generators
bootstrap seeds: 11, 22, 33 with fixed block-size configs
```

If compute is constrained, use five RL seeds and one generator seed for P0/P1. If deep models are promoted, use at least three generator seeds because generator instability itself is part of risk.

### 6.6 Cost scenarios

Use the same cost/slippage framework as Stage B, plus a Phase 4 stress matrix:

```text
cost_scenario_0_nominal:
  current Stage B nominal spread/fee/slippage

cost_scenario_1_conservative:
  nominal cost * 1.5 to 2.0

cost_scenario_2_stress:
  nominal cost * 3.0 or explicit high-volatility slippage model

cost_scenario_3_turnover_penalty:
  additional penalty proportional to turnover
```

Promotion is invalid if the synthetic-augmented policy improves zero-cost return but fails realistic or stress costs.

### 6.7 DSR/PBO/CSCV treatment

Every synthetic generator × integration method × candidate × seed group is a tested variant.

Required treatment:

```text
include Phase 4 arms in the multiple-testing ledger
compute DSR on real validation results only
compute PBO/CSCV where feasible across the expanded variant family
report the number of synthetic trials even if they failed
separate generator-selection trials from RL-policy trials
```

If 20 synthetic variants are tried and one looks good, that is not evidence until DSR/PBO accounting says it survives selection bias.

### 6.8 Promotion rules

Promote a synthetic augmentation to final Stage C eligibility only if all are true:

```text
1. beats real-only Stage B reproduction on real validation;
2. beats stationary/bootstrap baseline, not only an unaugmented baseline;
3. improves DSR or keeps DSR materially similar while reducing drawdown/tail risk;
4. does not worsen conservative/stress cost results;
5. reduces seed variance or improves worst-seed behavior;
6. does not increase turnover beyond pre-registered limit;
7. passes nearest-neighbor and leakage checks;
8. passes feature-family correlation/consistency checks;
9. generator and RL configs are frozen before Stage C;
10. Stage C is run once and only once.
```

### 6.9 Kill rules

Kill a generator family if any of the following occur:

```text
OHLCV validity violations > 0 after reconstruction
feature recomputation inconsistency detected
synthetic data copies long real windows
real-vs-synthetic classifier easily separates due to missing tails or broken volatility
squared-return autocorrelation materially worse than bootstrap
drawdown distribution is unrealistic
real validation uplift is negative for two candidate configs
improvement exists only under zero-cost evaluation
turnover increases materially without risk-adjusted compensation
DSR/PBO flags expanded search as likely false discovery
```

---

## 7. Implementation architecture for `financial-data`

### 7.1 Proposed module layout

```text
financial-data/
├── configs/
│   └── synthetic/
│       ├── default.yaml
│       ├── ethusdt_4h_sac_tech_stat.yaml
│       ├── generators/
│       │   ├── stationary_bootstrap.yaml
│       │   ├── regime_bootstrap.yaml
│       │   ├── walk_forward_residual.yaml
│       │   ├── hmm_garch.yaml
│       │   ├── timevae.yaml
│       │   └── diffusion.yaml
│       └── validation/
│           ├── stylized_facts.yaml
│           ├── nearest_neighbor.yaml
│           └── rl_uplift.yaml
│
├── src/
│   └── financial_data/
│       └── synthetic/
│           ├── __init__.py
│           ├── cli.py
│           ├── interfaces.py
│           ├── schema.py
│           ├── transforms.py
│           ├── reconstruction.py
│           ├── feature_recompute.py
│           ├── registry.py
│           ├── splitting.py
│           ├── generators/
│           │   ├── __init__.py
│           │   ├── base.py
│           │   ├── stationary_bootstrap.py
│           │   ├── regime_bootstrap.py
│           │   ├── walk_forward_residual.py
│           │   ├── hmm_garch.py
│           │   ├── timevae.py
│           │   ├── sigwgan.py
│           │   └── diffusion.py
│           ├── validators/
│           │   ├── __init__.py
│           │   ├── ohlcv_integrity.py
│           │   ├── stylized_facts.py
│           │   ├── autocorrelation.py
│           │   ├── drawdown.py
│           │   ├── regime_coverage.py
│           │   ├── feature_consistency.py
│           │   ├── nearest_neighbor.py
│           │   ├── leakage.py
│           │   └── rl_uplift.py
│           ├── reports/
│           │   ├── markdown.py
│           │   └── tables.py
│           └── agent_multi_adapter/
│               ├── __init__.py
│               ├── export_configs.py
│               ├── curriculum.py
│               └── run_manifest.py
│
├── synthetic_artifacts/
│   ├── README.md
│   ├── registry.jsonl
│   └── <dataset_id>/
│       ├── manifest.json
│       ├── generator_config.yaml
│       ├── input_hashes.json
│       ├── fit_report.md
│       ├── validation_report.md
│       ├── synthetic_ohlcv.parquet
│       ├── recomputed_features.parquet
│       ├── nearest_neighbor_report.json
│       └── stylized_facts_report.json
│
└── experiments/
    └── phase4_synthetic_augmentation/
        ├── design/
        │   ├── pre_registered_phase4_design.md
        │   ├── candidate_selection.md
        │   ├── generator_trial_ledger.md
        │   └── forbidden_practices.md
        ├── runs/
        ├── reports/
        └── phase4_summary.md
```

### 7.2 Core interfaces

```text
BaseSyntheticGenerator
  fit(real_ohlcv, context, config) -> FitArtifact
  sample(n_episodes, horizon, seed, conditions) -> SyntheticPrimitiveArtifact
  save(path) -> None
  load(path) -> BaseSyntheticGenerator

OHLCVReconstructor
  reconstruct(transformed_primitives, initial_state) -> ohlcv_dataframe
  validate_constraints(ohlcv_dataframe) -> ConstraintReport

FeatureRecomputer
  recompute(ohlcv_dataframe, feature_preset, fit_context) -> feature_dataframe

SyntheticValidator
  validate(real_train, synthetic, real_validation, config) -> ValidationReport

ArtifactRegistry
  register_dataset(manifest) -> dataset_id
  register_run(manifest) -> run_id
  assert_no_stage_c_dependency(manifest) -> bool
```

### 7.3 CLI commands

```text
fd-synth fit \
  --config configs/synthetic/ethusdt_4h_sac_tech_stat.yaml \
  --generator regime_bootstrap \
  --train-window pre_stage_c_train \
  --output synthetic_artifacts/

fd-synth sample \
  --dataset-id <fit_artifact_id> \
  --n-episodes 500 \
  --horizon 512 \
  --seed 11

fd-synth validate \
  --synthetic-dataset-id <dataset_id> \
  --real-validation-split stage_b_validation \
  --report reports/<dataset_id>_validation.md

fd-synth make-rl-dataset \
  --synthetic-dataset-id <dataset_id> \
  --feature-preset tech_stat \
  --integration pretrain_then_real_finetune

fd-synth export-agent-multi \
  --phase4-run-id <run_id> \
  --output ../agent-multi/configs/project3_phase4/<run_id>.yaml

fd-synth compare-uplift \
  --baseline-run real_only_stage_b_reproduction \
  --augmented-run synthetic_augmented_run \
  --metrics sharpe,sortino,calmar,drawdown,turnover,dsr,pbo
```

### 7.4 Output formats

Use immutable, hashable artifacts:

```text
Parquet:
  synthetic_ohlcv.parquet
  recomputed_features.parquet
  rl_episode_index.parquet

JSON:
  manifest.json
  input_hashes.json
  split_contract.json
  leakage_report.json
  nearest_neighbor_report.json
  stylized_facts_report.json
  rl_uplift_metrics.json

YAML:
  generator_config.yaml
  agent_multi_training_config.yaml

Markdown:
  fit_report.md
  validation_report.md
  phase4_candidate_report.md
```

### 7.5 Integration with `agent-multi`

Export configs that make the synthetic intervention explicit:

```yaml
project: project3
phase: phase4_synthetic_augmentation
candidate_id: ethusdt_4h_sac_tech_stat_stageb_candidate
asset: ethusdt
timeframe: 4h
algorithm: SAC
feature_preset: tech_stat
stage_c_forbidden: true

training_data:
  real_train_uri: features/trading_asset_features/ethusdt/4h/tech_stat.parquet
  synthetic_dataset_id: synth_v1_regime_bootstrap_ethusdt_4h_tech_stat_seed11
  integration_mode: pretrain_then_real_finetune
  synthetic_pretrain_steps: 250000
  real_finetune_steps: 500000
  final_training_phase_real_only: true

validation:
  validation_uri: experiments/stage_b_validation/splits/ethusdt_4h_validation.parquet
  synthetic_validation_forbidden: true

costs:
  scenario: conservative
  slippage_model: project3_stageb_default

ledger:
  immutable_run_ledger_required: true
  generator_manifest_required: true
  include_in_multiple_testing_ledger: true
```

---

## 8. Prioritized roadmap

### P0 — Mandatory governance and baseline generator layer

Estimated effort: **3–5 engineering days**.

Tasks:

1. Write `pre_registered_phase4_design.md`.
2. Implement primitive-vs-derived schema contract.
3. Implement OHLCV transform/reconstruction layer.
4. Implement stationary/bootstrap generator.
5. Implement regime-conditioned bootstrap.
6. Implement validation reports.
7. Implement artifact registry and hash manifests.
8. Implement Stage C dependency assertions.

Acceptance criteria:

```text
0 OHLCV constraint violations
0 direct generation of deterministic derived indicators
100% artifacts include split contract and input hashes
validation report generated for ETHUSDT 4h
nearest-neighbor report generated
real-only Stage B reproduction config exported to agent-multi
stationary/bootstrap synthetic run can be paired with real-only baseline
```

Kill condition:

```text
If P0 cannot prove no Stage C dependency, Phase 4 must not start.
```

### P1 — Practical augmentation experiment

Estimated effort: **1–2 weeks**.

Tasks:

1. Add walk-forward residual bootstrap.
2. Add HMM/GARCH or regime-GARCH generator.
3. Add conditional TimeVAE/CVAE generator.
4. Run Phase 4 on top 1–3 Stage B candidates.
5. Compare pretraining-only and conservative mixed curriculum.
6. Run 5 RL seeds per candidate/arm.
7. Run nominal, conservative, and stress cost scenarios.
8. Compute DSR/PBO/CSCV treatment with synthetic trials included.

Acceptance criteria:

```text
synthetic pretraining beats real-only validation on at least one top Stage B candidate
improvement beats stationary/bootstrap baseline
DSR improves or drawdown/tail risk improves without DSR degradation
cost-stress results do not degrade
seed variance decreases or worst-seed behavior improves
turnover does not materially increase
```

Kill condition:

```text
If no P1 method improves real validation robustness versus bootstrap and real-only baselines, defer deep synthetic generation.
```

### P2 — Advanced SOTA generator lane

Estimated effort: **2–6 weeks depending on compute and implementation depth**.

Tasks:

1. Implement Sig-Wasserstein GAN or COT-GAN.
2. Implement diffusion generator candidate:
   - Diffusion-TS-style general model; or
   - FTS-Diffusion-style financial pattern model; or
   - CoFinDiff-style controllable financial diffusion.
3. Add stricter memorization checks for deep models.
4. Add multi-asset/cross-asset conditioning if 15m/perp candidates need it.
5. Add order-flow/microstructure simulator only for 15m/perp if real LOB/spread data exists.

Acceptance criteria:

```text
deep method beats P0/P1 baselines, not only real-only baseline
passes stricter nearest-neighbor and tail checks
does not undergenerate rare regimes
does not create feature-correlation artifacts
improvement survives conservative/stress costs
configs are frozen before any Stage C evaluation
```

Kill condition:

```text
If deep generator improves synthetic metrics but not real validation RL robustness, it is a research artifact, not a trading augmentation.
```

---

## 9. Final decision

Add synthetic data generation, but only as a tightly governed Phase 4 lane.

Recommended first implementation:

```text
P0:
  primitive OHLCV generator interface
  stationary/block bootstrap
  regime-conditioned bootstrap
  validation suite
  artifact registry
  Stage C firewall checks

P1:
  walk-forward residual bootstrap
  HMM/GARCH generator
  conditional TimeVAE/CVAE
  paired real-validation RL uplift test

P2:
  Sig-Wasserstein GAN / COT-GAN
  conditional diffusion / FTS-Diffusion / CoFinDiff-style methods
  microstructure simulation for 15m/perp only
```

The strongest rule is:

> Synthetic data may improve training, stress testing, and robustness, but only real validation and the single untouched Stage C held-out evaluation can support a trading-performance claim.

---

## References and implementation sources

1. Politis, D. N., & Romano, J. P. (1994). *The Stationary Bootstrap.* https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf
2. Bollerslev, T. (1986). *Generalized Autoregressive Conditional Heteroskedasticity.* https://public.econ.duke.edu/~boller/Published_Papers/joe_86.pdf
3. Hamilton, J. D. (1989). *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle.* https://www.ssc.wisc.edu/~bhansen/718/Hamilton1989.pdf
4. Cont, R. (2001). *Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues.* https://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf
5. Yoon, J., Jarrett, D., & van der Schaar, M. (2019). *Time-series Generative Adversarial Networks.* https://papers.neurips.cc/paper/8789-time-series-generative-adversarial-networks.pdf
6. TimeGAN official code. https://github.com/jsyoon0823/TimeGAN
7. Lin, Z. et al. (2019). *Using GANs for Sharing Networked Time Series Data / DoppelGANger.* https://arxiv.org/abs/1909.13403
8. Xu, T. et al. (2020). *COT-GAN: Generating Sequential Data via Causal Optimal Transport.* https://arxiv.org/abs/2006.08571
9. COT-GAN official code. https://github.com/tianlinxu312/cot-gan
10. Ni, H. et al. (2021). *Sig-Wasserstein GANs for Time Series Generation.* https://arxiv.org/abs/2111.01207
11. Liao, S. et al. (2024). *Sig-Wasserstein GANs for Conditional Time Series Generation.* https://onlinelibrary.wiley.com/doi/full/10.1111/mafi.12423
12. Desai, A. et al. (2021). *TimeVAE: A Variational Auto-Encoder for Multivariate Time Series Generation.* https://arxiv.org/abs/2111.08095
13. Rasul, K. et al. (2021). *Autoregressive Denoising Diffusion Models for Multivariate Probabilistic Time Series Forecasting / TimeGrad.* https://arxiv.org/abs/2101.12072
14. Tashiro, Y. et al. (2021). *CSDI: Conditional Score-based Diffusion Models for Probabilistic Time Series Imputation.* https://arxiv.org/abs/2107.03502
15. CSDI official code. https://github.com/ermongroup/CSDI
16. Yuan, X., & Qiao, Y. (2024). *Diffusion-TS: Interpretable Diffusion for General Time Series Generation.* https://arxiv.org/abs/2403.01742
17. Diffusion-TS official code. https://github.com/Y-debug-sys/Diffusion-TS
18. Huang, H. et al. (2024). *Generative Learning for Financial Time Series with Irregular and Scale-Invariant Patterns / FTS-Diffusion.* https://openreview.net/forum?id=CdjnzWsQax
19. Takahashi, T., & Mizuno, T. (2024/2025). *Generation of Synthetic Financial Time Series by Diffusion Models.* https://arxiv.org/abs/2410.18897
20. Lee, D. et al. (2023). *Vector Quantized Time Series Generation with a Bidirectional Prior Model / TimeVQVAE.* https://proceedings.mlr.press/v206/lee23d.html
21. TimeVQVAE official code. https://github.com/ML4ITS/TimeVQVAE
22. Bao, Y. et al. (2024). *Towards Controllable Time Series Generation.* https://arxiv.org/abs/2403.03698
23. Tanaka, Y. et al. (2025). *CoFinDiff: Controllable Financial Diffusion Model for Time Series Generation.* https://www.ijcai.org/proceedings/2025/1040.pdf
24. Byrd, D. et al. (2019/2020). *ABIDES: Towards High-Fidelity Market Simulation for AI Research.* https://arxiv.org/abs/1904.12066
25. ABIDES official repository. https://github.com/abides-sim/abides
26. Frey, S. et al. (2023). *JAX-LOB: A GPU-Accelerated Limit Order Book Simulator to Unlock Large Scale Reinforcement Learning for Trading.* https://arxiv.org/abs/2308.13289
27. JAX-LOB official repository. https://github.com/KangOxford/jax-lob
28. Cont, R., Kukanov, A., & Stoikov, S. (2014). *The Price Impact of Order Book Events.* https://arxiv.org/abs/1011.6402
29. Gould, M. D. et al. (2013). *Limit Order Books.* https://www.math.ucla.edu/~mason/papers/gould-qf-final.pdf
30. Bailey, D. H., & López de Prado, M. (2014). *The Deflated Sharpe Ratio.* https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
31. Bailey, D. H. et al. (2015). *The Probability of Backtest Overfitting.* https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
32. Esteban, C., Hyland, S. L., & Rätsch, G. (2017). *Real-valued Medical Time Series Generation with Recurrent Conditional GANs; TSTR evaluation.* https://arxiv.org/abs/1706.02633
33. Synthetic Data Privacy Metrics survey / NNDR and DCR discussion. https://arxiv.org/html/2501.03941v1
