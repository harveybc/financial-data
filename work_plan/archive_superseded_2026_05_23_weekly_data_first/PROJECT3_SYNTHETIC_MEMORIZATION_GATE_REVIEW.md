# Project 3 Phase 4 Synthetic Time-Series Augmentation — Memorization Gate Review

**Role:** skeptical senior quant ML researcher and reviewer  
**Focus:** anti-memorization review of `regime_residual_bootstrap_v1` for `ETHUSDT 4h`, and governance recommendations for Project 3 Phase 4 synthetic augmentation  
**Date:** 2026-05-03  
**Held-out firewall:** `2025-01-01+` must not be used for generator training, tuning, validation, threshold calibration, prompt context, or synthetic-data evaluation design. Stage C remains untouched until final locked evaluation.

---

## 1. Executive verdict

### 1.1 Current result summary

Current synthetic generator result for `regime_residual_bootstrap_v1`, `ETHUSDT 4h`:

| Test | Result | Status | Reviewer interpretation |
|---|---:|---|---|
| `algebraic_violations` | `0` | PASS | Good. OHLCV reconstruction constraints are holding. |
| `ks_returns_p_value` | `0.079` | PASS | Borderline statistical pass. Do not over-trust p-values; also inspect effect sizes, tails, and regime-specific distances. |
| `wasserstein_ratio` | `0.032` | PASS | Good marginal return-distance result if ratio definition is stable across datasets. |
| `classifier_auc` | `0.588` | PASS | Acceptable. Slightly distinguishable but not obviously fake. |
| `nn_overlap_rate` | `0.000` | PASS | Good, assuming nearest-neighbor metric is computed on transformed primitive windows, not on recomputed derived features only. |
| `copied_subseq_ratio` | `0.000` | PASS | Good, assuming subsequence length is economically meaningful. |
| `duplicate_window_rate` | `0.015` | FAIL vs `0.001` | Needs decomposition. This is not automatically a fatal flaw for a bootstrap-family generator, but it is **not ready for RL consumption until clarified and mitigated**. |

### 1.2 Main recommendation

`regime_residual_bootstrap_v1` is **promising but not yet cleared for RL augmentation**. The current `duplicate_window_rate = 0.015` should trigger a **conditional no-go** until the metric is decomposed into:

1. **synthetic–synthetic duplicate windows**, meaning the generator repeats its own generated windows;
2. **synthetic–train exact-copy windows**, meaning generated windows are exact copies of real train-period windows;
3. **synthetic–validation or synthetic–held-out copies**, which must be a hard fail;
4. duplicate rates by **window length**, especially at the RL observation horizon;
5. duplicate rates computed on **transformed primitive OHLCV**, not directly on deterministic technical indicators.

If the 1.5% duplicate rate is mostly **synthetic–synthetic duplication of short bootstrap windows**, it should be a warning and diversity issue, not a hard scientific rejection. If it is **exact copying of train-period windows at or above the SAC observation horizon**, it should be treated as a hard fail for training augmentation until fixed.

### 1.3 Why this matters

Synthetic data may train or pretrain Project 3 policies, but it must never serve as evidence of tradability. Project 3 is explicitly designed as a data-centric RL evaluation pipeline where fixed PPO/SAC/DQN configurations are compared across trading asset, simulation timeframe, feature input set, and feature-engineering technique. Synthetic augmentation must preserve that design rather than create a hidden second optimizer.

The current feature sample contains primitive OHLCV plus many deterministic technical/statistical columns such as `typical_price`, returns, log returns, moving averages, MACD, RSI, Bollinger bands, ATR/NATR, OBV, VWAP, rolling moments, realized variance, autocorrelations, volatility-regime flags, Hurst proxy, and z-score features. Therefore, anti-memorization tests should be applied to generated **primitive transformed paths** and RL observation windows, while deterministic features should be recomputed causally from synthetic OHLCV.

---

## 2. Is `duplicate_window_rate <= 0.001` statistically and practically appropriate?

### 2.1 Short answer

A universal hard threshold of `duplicate_window_rate <= 0.001` is **too strict and statistically under-specified** for block-bootstrap-like generators if it counts synthetic–synthetic duplicate windows or short windows. It is **reasonable as a hard threshold** only when it measures exact synthetic copies of real train windows at a meaningful length, especially the RL observation horizon.

### 2.2 Why the raw threshold is under-specified

A duplicate-window metric is not interpretable unless the report defines:

```text
window_length_bars
feature_space_used_for_hashing_or_distance
exact_match_tolerance
whether duplicates are synthetic-synthetic, synthetic-train, synthetic-validation, or synthetic-heldout
whether windows are overlapping
whether windows are measured before or after OHLCV reconstruction
whether deterministic technical indicators are included
whether values are raw, rounded, quantized, rank-transformed, or robust-scaled
```

For a 4h bar series, eight years of data are only about:

```text
6 bars/day × 365 days/year × 8 years ≈ 17,520 bars
```

If the RL observation window is 32 to 128 bars, the number of economically distinct train windows is not huge. A bootstrap generator that samples with replacement from finite blocks can naturally repeat blocks. This is one reason why a raw `0.001` threshold can reject the generator class rather than detect genuine leakage.

### 2.3 Expected duplicate rate under finite block resampling

For a simplified bootstrap that samples `M` blocks from `N` possible source blocks with replacement and uniform probability, the expected number of unique selected blocks is approximately:

```text
E[unique] = N × (1 - (1 - 1/N)^M)
```

The expected duplicate fraction is approximately:

```text
duplicate_fraction ≈ 1 - E[unique] / M
```

For non-uniform regime-conditioned sampling, expected duplicate pairs are driven by concentration:

```text
E[duplicate_pairs] ≈ C(M, 2) × Σ_i p_i²
```

where `p_i` is the probability of selecting source block `i`. If one regime is rare and oversampled, duplicates can rise even when there is no held-out leakage.

### 2.4 Practical interpretation for the current `0.015`

The current `duplicate_window_rate = 0.015` means roughly 1.5% of measured windows are duplicates under the current metric. This should be interpreted as follows:

| Metric meaning | Interpretation of `0.015` | Decision |
|---|---|---|
| Synthetic–synthetic duplicate short windows | Mild to moderate diversity problem | Warning; mitigate but not immediate rejection |
| Synthetic–synthetic duplicate full RL observation windows | Material diversity problem | No-go until reduced or justified by null calibration |
| Synthetic–train exact copied windows shorter than block length | Expected for naive bootstrap; bad for augmentation value | Warning or no-go depending length and frequency |
| Synthetic–train exact copied full observation windows | Overfit/memorization risk | Hard fail for RL augmentation |
| Synthetic–validation or synthetic–held-out copied windows | Leakage | Hard fail, regardless of rate |

### 2.5 Recommended threshold policy

Do not use one threshold. Use generator-class-aware thresholds and window-length-aware gates.

#### 2.5.1 For non-bootstrap deep generators

| Metric | Pass | Warning | Hard fail |
|---|---:|---:|---:|
| Exact synthetic–train copied windows at RL observation horizon | `<= 0.001` | `0.001–0.005` | `> 0.005` |
| Synthetic–synthetic duplicate full windows | `<= 0.001` | `0.001–0.005` | `> 0.005` |
| Copied subsequence ratio, long subsequences | `<= 0.001` | `0.001–0.003` | `> 0.003` |
| Synthetic–validation/held-out exact copies | `0` | none | `> 0` |

#### 2.5.2 For bootstrap and residual-bootstrap generators

| Metric | Pass | Warning | Hard fail |
|---|---:|---:|---:|
| Synthetic–synthetic duplicate short windows | `<= 0.005` | `0.005–0.02` | `> 0.02` |
| Synthetic–synthetic duplicate full observation windows | `<= 0.003` | `0.003–0.01` | `> 0.01` |
| Synthetic–train exact full observation-window copies | `<= 0.001` | `0.001–0.005` | `> 0.005` |
| Long copied subsequence ratio | `<= 0.001` | `0.001–0.003` | `> 0.003` |
| Synthetic–validation/held-out exact copies | `0` | none | `> 0` |

Under this policy, the current `0.015` is:

```text
- warning if it is synthetic-synthetic short-window duplication;
- hard fail if it is synthetic-train full-observation copying;
- hard fail if any part touches validation or held-out;
- insufficiently specified as currently reported.
```

---

## 3. Better anti-memorization metrics for synthetic financial time series

### 3.1 Required metric decomposition

Replace a single `duplicate_window_rate` with this metric family:

```text
duplicate_window_rate_synth_synth[k]
duplicate_window_rate_synth_train[k]
duplicate_window_rate_synth_validation[k]
duplicate_window_rate_synth_heldout[k]
near_duplicate_rate_synth_train[k, metric]
longest_copied_subsequence_bars
source_block_reuse_entropy
source_block_reuse_gini
effective_unique_window_count[k]
effective_sample_size_ratio[k]
```

Evaluate at multiple window lengths:

```text
k ∈ {4, 8, 16, 32, 64, observation_window_bars, 2 × observation_window_bars}
```

For `ETHUSDT 4h`, practical first defaults:

```text
short: 8 bars     ≈ 1.3 days
medium: 32 bars   ≈ 5.3 days
long: 64 bars     ≈ 10.7 days
very long: 128 bars ≈ 21.3 days
```

### 3.2 Exact-copy metrics

Use exact-copy metrics only after canonicalization:

```text
1. work on transformed primitive variables:
   - close log return
   - open-to-previous-close log gap
   - high distance above max(open, close)
   - low distance below min(open, close)
   - log1p(volume)

2. robust-scale using train-only scalers;

3. optionally quantize to fixed precision:
   - exact numeric hash: strict copy check
   - quantile-bin hash: near-copy check
   - sign/rank hash: structural-copy check
```

Do **not** use deterministic indicator columns as the primary memorization surface. Technical indicators can amplify small OHLCV copies into many duplicated derived columns.

### 3.3 Distance-based privacy and memorization metrics

Recommended distance metrics:

| Metric | Purpose | Gate role |
|---|---|---|
| Distance to closest train record/window, DCR | Detect near copies | Warning/hard fail depending lower-tail distance |
| Nearest-neighbor distance ratio, NNDR | Detect whether synthetic points lie too close to train relative to local density | Warning/hard fail |
| Synthetic-to-train vs validation-to-train distance comparison | Calibrate whether synthetic is closer to train than real unseen validation | Hard gate if synthetic is materially closer |
| Membership-inference attack score | Test whether synthetic set reveals train membership | P1/P2 privacy gate |
| Longest common subsequence over quantized returns | Detect copied return-sign/rank paths | Hard gate if long |
| Dynamic time warping lower-tail distance | Detect shifted/warped path copies | Diagnostic/warning |
| Signature-distance lower-tail | Path-level near-copy check | P1/P2 diagnostic |

Distance-based nearest-neighbor memorization checks are common but imperfect: van den Burg and Williams note that nearest-neighbor comparisons are a common memorization diagnostic for generative models, while also warning that simple metrics can miss transformed copies. Therefore, Project 3 should combine exact hashes, lower-tail distance metrics, NNDR/DCR-style metrics, and generated-window source-block reuse analysis. See: [van den Burg & Williams, 2021, *On Memorization in Probabilistic Deep Generative Models*](https://proceedings.neurips.cc/paper_files/paper/2021/file/eae15aabaa768ae4a5993a8a4f4fa6e4-Paper.pdf). Distance-based privacy metrics such as DCR, NNDR, and attack-based measures are also discussed in recent synthetic-data privacy reviews. See: [Synthetic Data Privacy Metrics, 2025](https://arxiv.org/html/2501.03941v1).

### 3.4 Financial-path-specific memorization metrics

Generic duplicate metrics are not enough. For financial OHLCV, add:

#### 3.4.1 Source block reuse entropy

```text
source_block_reuse_entropy = -Σ_i p_i log(p_i)
normalized_entropy = entropy / log(number_of_source_blocks)
```

Gate:

```text
pass:    normalized_entropy >= 0.85
warning: 0.70 <= normalized_entropy < 0.85
fail:    normalized_entropy < 0.70
```

#### 3.4.2 Source block max-reuse cap

```text
max_source_block_reuse_rate = max_i count(source_block_i) / total_sampled_blocks
```

Gate:

```text
pass:    <= 0.005
warning: 0.005–0.02
fail:    > 0.02
```

#### 3.4.3 Effective unique observation windows

```text
effective_unique_window_ratio[k] = unique_synthetic_windows[k] / total_synthetic_windows[k]
```

Gate for `k = observation_window_bars`:

```text
pass:    >= 0.995 for deep generators; >= 0.990 for residual bootstrap
warning: 0.980–0.990 for residual bootstrap
fail:    < 0.980
```

#### 3.4.4 Train-distance lower-tail calibration

Compare synthetic-to-train distances with validation-to-train distances:

```text
D_syn_train = distance(each synthetic window, nearest train window)
D_val_train = distance(each validation window, nearest train window)
```

Gate:

```text
hard fail if quantile_1pct(D_syn_train) < 0.5 × quantile_1pct(D_val_train)
warning   if quantile_1pct(D_syn_train) < 0.8 × quantile_1pct(D_val_train)
pass      if synthetic lower-tail distances are comparable to validation lower-tail distances
```

This is more meaningful than an absolute threshold because it asks whether the synthetic generator is **closer to training history than naturally unseen real data is**.

#### 3.4.5 Strategy-reward duplicate windows

Since the purpose is RL training, evaluate duplication in the space that matters to the policy:

```text
observation_window_hash
reward_window_hash
cost_adjusted_return_path_hash
action-relevant_feature_hash
```

A generator can pass OHLCV-level duplication tests and still repeat nearly identical reward/observation windows.

---

## 4. Gate hierarchy: hard fail vs warning vs diagnostic

### 4.1 Hard-fail gates

Synthetic data must be rejected for RL training if any hard gate fails:

| Gate | Hard fail condition |
|---|---|
| Held-out firewall | Any data at or after `2025-01-01` used for generator fitting, scaler fitting, threshold tuning, metric threshold selection, prompt context, or dataset design. |
| Stage C isolation | Synthetic data, synthetic metrics, or generator artifacts touch Stage C before final locked evaluation. |
| Validation leakage | Generator is fit or tuned on validation rows. |
| Algebraic validity | Any OHLCV algebraic violation after reconstruction. |
| Synthetic–heldout copy | Any exact or near-exact copied held-out window. |
| Synthetic–validation copy | Any exact or near-exact copied validation window. |
| Train full-window copying | Synthetic–train exact copies exceed threshold at RL observation horizon. |
| Long copied subsequence | Long copied subsequence ratio exceeds threshold. |
| Feature inconsistency | Derived indicators are generated directly and inconsistent with primitive OHLCV recomputation. |
| Cost-blind promotion | Generator only improves pre-cost metrics but fails cost/slippage gates. |
| Unlogged search | Generator variants or thresholds are not charged as tested strategy families. |

### 4.2 Warning gates

Warnings do not automatically reject the generator, but they block promotion until documented:

| Warning | Interpretation |
|---|---|
| Synthetic–synthetic duplicate short-window rate in `0.005–0.02` | May be acceptable for bootstrap, but reduces augmentation diversity. |
| Classifier AUC `0.60–0.70` | Synthetic distribution is distinguishable; inspect why. |
| KS p-value barely above `0.05` | Borderline marginal return fit; inspect tails. |
| Regime occupancy mismatch | Generator may be oversampling or undersampling regimes. |
| High block reuse concentration | Synthetic set may overrepresent a few historic episodes. |
| OOD validation distance | Synthetic lower-tail distance too close to train vs validation. |
| Duplicate technical rows | May be caused by deterministic recomputation; inspect primitive path duplicates instead. |

### 4.3 Diagnostic metrics

Diagnostics are reported but not used as pass/fail gates alone:

```text
real-vs-synthetic classifier feature importance
MMD / signature-MMD path distance
DTW distance distribution
ACF / PACF distance by lag
squared-return ACF distance
rolling drawdown distribution
rolling volatility regime occupancy
block boundary jump distribution
synthetic feature-correlation heatmap
visual overlays of sampled windows
TSTR / TRTS predictive tests
```

TimeGAN popularized discriminative and predictive scores for time-series synthetic evaluation, but those should not be the only criteria for financial RL augmentation. See: [Yoon, Jarrett & van der Schaar, 2019, *Time-series Generative Adversarial Networks*](https://papers.nips.cc/paper/8789-time-series-generative-adversarial-networks).

---

## 5. Implementation techniques to reduce memorization without destroying realism

### 5.1 Improve residualization before resampling

Prefer residual bootstrap over raw block bootstrap:

```text
1. Estimate train-only regime state or volatility state.
2. Model conditional mean/volatility at each bar.
3. Compute standardized residuals.
4. Resample residual blocks inside compatible regimes.
5. Reconstruct returns using sampled/generated volatility and regime state.
6. Reconstruct valid OHLCV.
7. Recompute deterministic features causally.
```

This reduces exact copies because the sampled object is residual structure, not raw price path.

### 5.2 Use variable-length blocks with reuse caps

Use stationary-bootstrap-style variable blocks, but cap reuse:

```text
block_length ~ geometric(p)
source_block_reuse_count[i] <= max_reuse
source_block_cooldown prevents immediate repeated blocks
regime sampling probability is smoothed to avoid rare-regime over-copying
```

The stationary bootstrap was designed for weakly dependent stationary observations and is less rigid than fixed-length block resampling. See: [Politis & Romano, 1994, *The Stationary Bootstrap*](https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf). However, a naive stationary bootstrap can still memorize if it resamples long blocks without perturbation.

### 5.3 Add constrained residual jitter

Add noise in transformed residual space, not in raw OHLCV:

```text
r_close_t' = r_close_t + ε_return
r_open_t'  = r_open_t  + ε_open_gap
range_hi'  = softplus(range_hi_residual + ε_hi)
range_lo'  = softplus(range_lo_residual + ε_lo)
volume'    = log1p_volume_residual + ε_volume
```

Use regime-conditioned Student-t or empirical residual noise:

```text
ε ~ StudentT(df_regime, scale_regime × jitter_strength)
```

Start conservatively:

```text
jitter_strength ∈ {0.02, 0.05, 0.10} of train-regime residual scale
```

Do not tune jitter on held-out. Tune only on train-inner validation or freeze a small grid and count each variant as a tested generator family.

### 5.4 Use rejection sampling against train-window copies

After generation:

```text
for each synthetic window at k = observation_window_bars:
    compute nearest train-window distance
    reject if exact or too close under train-calibrated threshold
```

Important: rejection thresholds must be calibrated on train-only distributions, not validation or held-out.

### 5.5 Distort source blocks in economically valid ways

Useful transformations:

```text
volatility rescaling within regime quantile bounds
rank-preserving residual perturbation
small random time warping inside block only if bar spacing remains valid
randomized block boundary bridge to avoid unnatural jumps
conditional volume residual perturbation
range residual perturbation while preserving OHLC constraints
```

Avoid transformations that destroy stylized facts:

```text
large iid Gaussian noise on returns
row shuffling
independent OHLC generation
independent generation of technical indicators
heavy smoothing that removes tails and volatility clustering
```

### 5.6 Generate at primitive level only

The generator should emit transformed primitive OHLCV paths:

```text
log_close_return
log_open_gap
high_distance_from_max_open_close
low_distance_from_min_open_close
log1p_volume
optional regime/context state
```

Then reconstruct:

```text
OPEN_t  = CLOSE_{t-1} × exp(log_open_gap_t)
CLOSE_t = CLOSE_{t-1} × exp(log_close_return_t)
HIGH_t  = max(OPEN_t, CLOSE_t) × exp(nonnegative_high_distance_t)
LOW_t   = min(OPEN_t, CLOSE_t) × exp(-nonnegative_low_distance_t)
VOLUME_t = exp(log1p_volume_t) - 1
```

Finally recompute every deterministic feature causally.

---

## 6. Method comparison for Project 3 Phase 4

### 6.1 Scoring scale

```text
5 = excellent / highly suitable
4 = good
3 = acceptable with caveats
2 = weak or risky
1 = poor fit for this use case
```

### 6.2 Comparison table

| Method | Expected RL value | Effort | Leakage / memorization risk | Mode-collapse / overfit risk | Stylized facts | ETHUSDT 4h suitability | 15m crypto/perp suitability | FX suitability | Reviewer decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Regime residual bootstrap v1** | 4 | 2 | 3 | 2 | 4 | 4 | 3 | 3 | Best current P0 candidate, but duplicate metric must be decomposed and mitigated. |
| **Stationary/block bootstrap** | 3 | 1 | 4 | 1 | 4 | 3 | 2 | 3 | Keep as baseline; not enough for RL augmentation if memorization is high. |
| **Regime-conditioned bootstrap** | 3–4 | 2 | 3 | 1–2 | 4 | 4 | 3 | 3 | Useful P0/P1 baseline; must cap rare-regime block reuse. |
| **Walk-forward residual bootstrap** | 4 | 3 | 2–3 | 2 | 4 | 4 | 3 | 4 | Strong next implementation; better than raw block copying. |
| **GARCH / EGARCH / regime-GARCH** | 3 | 2–3 | 1 | 1 | 3 | 3 | 2 | 4 | Good econometric baseline; weak for complex path/volume dependencies. |
| **HMM / regime-switching generator** | 3 | 2 | 1–2 | 2 | 3 | 3–4 | 2–3 | 4 | Good for regime paths; pair with residual model. |
| **TimeGAN-style methods** | 3 | 4 | 3 | 4 | 3 | 2–3 | 2–3 | 2–3 | Useful benchmark, but GAN instability and mode collapse are material risks. |
| **TimeVAE / conditional VAE** | 3–4 | 3 | 2 | 2–3 | 3 | 4 | 3 | 3 | Good P1 deep model because it is stable and auditable. Beware smoothing tails. |
| **COT-GAN / optimal transport GAN** | 3–4 | 4 | 2–3 | 3 | 4 | 3 | 3 | 3 | Interesting P2; more principled sequential loss than vanilla GAN. |
| **Sig-Wasserstein GAN / SigCWGAN** | 4 | 4 | 2–3 | 3 | 4–5 | 4 | 3 | 4 | Strong finance-oriented P2 candidate; implementation complexity is nontrivial. |
| **Diffusion / score-based time-series generators** | 4–5 | 5 | 2–3 | 2–3 | 4–5 | 4 | 4 | 4 | Most promising future lane; not P0. Must beat residual bootstrap under real validation. |
| **CoFinDiff / controllable financial diffusion** | 4–5 | 5 | 2–3 | 2–3 | 4–5 | 4 | 4 | 4 | Very relevant 2025 direction; high implementation and governance burden. |
| **Synthetic order-flow / microstructure simulation** | 2 for 4h, 4 for 15m | 5 | 2 | 3 | 4 if calibrated | 1–2 | 4 | 2 | Defer. Useful for 5m/15m perps, not first ETHUSDT 4h lane. |

### 6.3 Method-specific critique

#### 6.3.1 Regime residual bootstrap

This is the best immediate method because it is auditable, cheap, and aligned with the purpose of stress/pretraining augmentation. It can preserve volatility clustering and regime structure better than pure iid perturbation. The current duplicate-window issue is fixable with source-block reuse caps, residual jitter, train-distance rejection, and better metric decomposition.

#### 6.3.2 Stationary/bootstrap family

Stationary and block bootstrap methods are valuable baselines for dependent time series. They preserve local dependence but copy by design, so exact duplication must be interpreted differently from deep-generator memorization. They should remain the **minimum benchmark**: a deep generator that cannot beat a controlled residual bootstrap in downstream real validation is not worth adding.

#### 6.3.3 GARCH/HMM baselines

GARCH remains essential because volatility clustering is central to financial returns. Bollerslev’s GARCH generalized ARCH by allowing lagged conditional variances in the volatility process. See: [Bollerslev, 1986, *Generalized Autoregressive Conditional Heteroskedasticity*](https://public.econ.duke.edu/~boller/Published_Papers/joe_86.pdf). Hamilton’s regime-switching framework is the classical econometric reference for latent regime changes in time series. See: [Hamilton, 1989](https://www.ssc.wisc.edu/~bhansen/718/Hamilton1989.pdf).

For Project 3, GARCH/HMM is a baseline and a component, not the final generator. It will likely under-model volume, range, nonlinear dynamics, and cross-feature structure.

#### 6.3.4 TimeGAN

TimeGAN combines adversarial training with a supervised temporal loss in a learned embedding space. It is a useful benchmark, but for financial RL it has two risks: mode collapse and underproduction of rare tail/crash regimes. See: [Yoon, Jarrett & van der Schaar, 2019](https://papers.nips.cc/paper/8789-time-series-generative-adversarial-networks).

#### 6.3.5 TimeVAE / CVAE

TimeVAE is attractive as the first deep model because it is more stable than adversarial training and can incorporate interpretable trend/seasonal components. See: [Desai et al., 2021, *TimeVAE*](https://arxiv.org/abs/2111.08095). For Project 3, a **conditional VAE over transformed primitive OHLCV** is a reasonable P1 candidate.

#### 6.3.6 COT-GAN and Sig-Wasserstein GAN

COT-GAN uses causal optimal transport to impose temporal causality in the generation objective. See: [Xu et al., 2020, *COT-GAN*](https://arxiv.org/abs/2006.08571). Sig-Wasserstein GANs use path signatures and Wasserstein-style metrics, which are especially relevant to ordered financial paths. See: [Ni et al., 2021, *Sig-Wasserstein GANs for Time Series Generation*](https://arxiv.org/abs/2111.01207) and [Liao et al., 2020/2023, *Conditional Sig-Wasserstein GANs*](https://arxiv.org/abs/2006.05421).

These are strong research candidates, but not the next implementation step until P0/P1 gates are mature.

#### 6.3.7 Diffusion and score-based generators

Diffusion models are the most promising advanced lane. Diffusion-TS proposes an interpretable diffusion framework using transformer-style temporal modeling and decomposition-guided representations. See: [Yuan & Qiao, 2024, *Diffusion-TS*](https://arxiv.org/abs/2403.01742). FTS-Diffusion is directly aimed at financial time-series generation and reports stronger resemblance to observed financial data than several baselines. See: [Huang et al., 2024, *Generative Learning for Financial Time Series*](https://proceedings.iclr.cc/paper_files/paper/2024/file/f90fc76b199fe6b0ec2a51aaf72c3277-Paper-Conference.pdf). CoFinDiff proposes controllable financial diffusion using conditional signals and cross-attention. See: [Tanaka et al., 2025, *CoFinDiff*](https://arxiv.org/abs/2503.04164).

The critique: diffusion is expensive, can still memorize, and increases experiment degrees of freedom. It should not be introduced before residual bootstrap, walk-forward residual bootstrap, and CVAE baselines are cleanly evaluated.

#### 6.3.8 Recent comparative evidence

A 2024 comparative review of deep generative methods for financial time series emphasizes that objectives should include variety, distributional similarity, dynamics, and financial backtesting KPIs; it compares CGAN, CWGAN, diffusion, Signature WGAN, and Conditional TimeVAE-style approaches. See: [Ericson et al., 2024, *Deep Generative Modeling for Financial Time Series with Application in VaR*](https://arxiv.org/abs/2401.10370).

---

## 7. Required validation before RL consumes synthetic data

### 7.1 Primitive-level validity

Hard gates:

```text
OHLC constraints:       HIGH >= max(OPEN, CLOSE), LOW <= min(OPEN, CLOSE)
positive prices:        OPEN, HIGH, LOW, CLOSE > 0
nonnegative volume:     VOLUME >= 0
feature recomputation:  all deterministic indicators recomputed from synthetic OHLCV
no NaNs after warm-up:  except explicit warm-up rows that are masked/dropped
```

### 7.2 Distribution and stylized-fact tests

Required tests:

```text
return distribution: mean, std, skew, kurtosis, quantiles, tail index
KS and Wasserstein on returns and log returns
volatility clustering: ACF of |returns| and squared returns
raw return autocorrelation
drawdown distribution
run-length distribution
regime occupancy and transition matrix
volume distribution and volume-return/volume-volatility relationship
OHLC range distribution
feature correlation matrix after recomputation
```

Financial returns are known to exhibit stylized facts such as heavy tails, volatility clustering, weak raw-return autocorrelation, and nonlinear dependence; synthetic paths must be checked against those properties rather than only marginal KS tests. See: [Cont, 2001, *Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues*](https://www-stat.wharton.upenn.edu/~steele/Resources/FTSResources/StylizedFacts/Cont2001.pdf).

### 7.3 Anti-memorization tests

Required:

```text
exact duplicate windows by k
near duplicate windows by k
synthetic-to-train distance distribution
validation-to-train distance null distribution
DCR / NNDR
longest copied subsequence
source-block reuse entropy and Gini
source block max-reuse rate
membership-inference-style diagnostic, P1+
```

### 7.4 Train/synthetic/validation separation

Hard gates:

```text
Generator fit uses train only.
Scaler/imputer/transform fit uses train only.
Thresholds are calibrated on train-inner split only.
Validation is used only for final Phase 4 comparison.
Held-out 2025+ is not used for anything before locked Stage C.
Synthetic data is never used as validation or Stage C evidence.
```

### 7.5 Downstream RL paired uplift test

Synthetic data may enter RL only after the above gates pass. The decisive test is:

```text
A. Real-only SAC + tech_stat
B. Real + stationary/bootstrap synthetic
C. Real + regime_residual_bootstrap_v1 synthetic
D. Real + mitigated regime_residual_bootstrap_v2 synthetic
```

Evaluate only on real validation data, never synthetic validation.

Promotion requires:

```text
net validation performance improves after costs
max drawdown improves or does not materially worsen
turnover does not materially increase
seed variance decreases or does not worsen
cost/slippage stress does not erase the uplift
DSR/PBO accounting includes every generator variant
```

DSR corrects for selection bias, non-normal returns, and multiple testing in Sharpe-like strategy evaluation; PBO/CSCV estimates backtest overfitting probability across strategy specifications. See: [Bailey & López de Prado, 2014, *The Deflated Sharpe Ratio*](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) and [Bailey et al., 2015, *The Probability of Backtest Overfitting*](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

---

## 8. Go/no-go recommendation for the current generator

### 8.1 Current status

```text
Current status: CONDITIONAL NO-GO FOR RL AUGMENTATION
Reason: duplicate_window_rate is failed and under-specified.
```

The generator is **not rejected as a concept**. It is rejected only for immediate RL consumption until duplicate metrics are decomposed and mitigated.

### 8.2 Go if all are true

```text
[ ] duplicate_window_rate is decomposed into synth-synth, synth-train, synth-validation, and synth-heldout
[ ] synthetic-validation duplicate rate = 0
[ ] synthetic-heldout duplicate rate = 0
[ ] synthetic-train exact full observation-window copy rate <= 0.001
[ ] synthetic-synthetic full observation-window duplicate rate <= 0.003, or justified by train-calibrated null
[ ] copied_subseq_ratio remains 0 or <= 0.001 for long subsequences
[ ] source-block normalized entropy >= 0.85, or warning accepted with documented reason
[ ] max source-block reuse rate <= 0.005, or warning accepted with documented reason
[ ] synthetic-to-train lower-tail distance is not materially smaller than validation-to-train lower-tail distance
[ ] all algebraic and feature-recomputation tests pass
[ ] all generator variants are logged as tested strategy families
```

### 8.3 No-go if any are true

```text
[ ] any post-2025 data is used
[ ] any Stage C artifact is touched
[ ] validation or heldout is used to tune duplicate thresholds
[ ] exact copied heldout/validation windows exist
[ ] full observation-window train copies exceed threshold
[ ] duplicate mitigation destroys return tails or volatility clustering
[ ] downstream RL only improves before costs
[ ] uplift appears only in one seed or one cost scenario
[ ] generator wins only after unlogged threshold/model search
```

---

## 9. Prioritized implementation plan

### P0 — repair metrics and current generator

**Estimated effort:** 2–4 engineering days

Tasks:

```text
1. Redefine duplicate_window_rate with explicit dimensions:
   - by k
   - synth-synth
   - synth-train
   - synth-validation
   - synth-heldout
   - exact vs quantized vs near-distance

2. Add source-block tracking:
   - source block ID
   - regime ID
   - block start/end timestamp
   - reuse count
   - block-boundary count

3. Add lower-tail nearest-neighbor calibration:
   - synthetic-to-train
   - validation-to-train
   - train-inner-to-train-neighbor null

4. Re-run current regime_residual_bootstrap_v1 metrics.

5. Implement v2 mitigations:
   - source reuse caps
   - residual jitter
   - train-distance rejection at observation horizon
   - rare-regime sampling smoothing
```

Acceptance criteria:

```text
- no heldout/validation usage
- all metric definitions documented
- duplicate metrics decomposed and thresholded
- v2 reduces dangerous full-window train copies without materially degrading KS/Wasserstein/tail/regime metrics
```

### P1 — build stronger auditable baselines

**Estimated effort:** 1–2 weeks

Tasks:

```text
1. Walk-forward residual bootstrap.
2. GARCH/HMM residual generator baseline.
3. Conditional TimeVAE/CVAE over transformed primitive OHLCV.
4. Same validation suite across all generators.
5. Same downstream real-validation RL paired comparison.
```

Acceptance criteria:

```text
- every generator beats or explains failure vs stationary bootstrap
- no generator uses validation/heldout for fitting
- real-only baseline remains the primary comparator
- generator family count included in DSR/PBO accounting
```

### P2 — advanced research lane

**Estimated effort:** 3–6+ weeks

Tasks:

```text
1. Sig-Wasserstein GAN or COT-GAN.
2. Diffusion-TS / FTS-Diffusion-style conditional generator.
3. CoFinDiff-style controllable generator if conditioning variables are mature.
4. Optional 15m/perp microstructure simulator only after 4h pipeline is stable.
```

Acceptance criteria:

```text
- advanced generator beats residual bootstrap and CVAE on real validation after costs
- it does not merely improve synthetic fidelity while hurting RL robustness
- compute cost and complexity are justified by paired validation uplift
```

---

## 10. Forbidden practices

The following practices are forbidden in Project 3 Phase 4:

```text
1. Training, fitting, scaling, thresholding, prompt construction, or synthetic-generation design using data >= 2025-01-01.
2. Allowing synthetic data or generator diagnostics to touch Stage C before final locked evaluation.
3. Treating synthetic validation performance as evidence of tradability.
4. Directly generating technical indicators instead of recomputing them from primitive synthetic OHLCV.
5. Selecting duplicate thresholds after looking at validation or held-out results.
6. Dropping bad validation windows as “OOD” and claiming improved performance.
7. Reporting a deep generator win unless it beats real-only and bootstrap/residual-bootstrap baselines.
8. Hiding failed generator attempts from DSR/PBO/CSCV accounting.
9. Using synthetic data to justify repeated Stage C runs.
10. Claiming profitability from synthetic-only backtests.
```

---

## 11. Final recommendation

### 11.1 Decision on the current `duplicate_window_rate <= 0.001` gate

The `<= 0.001` threshold is appropriate as a hard gate for:

```text
exact synthetic copies of train windows at the RL observation horizon;
long copied subsequences;
all synthetic-validation and synthetic-heldout copies, where the threshold should actually be zero.
```

It is too strict as a universal hard gate for:

```text
synthetic-synthetic duplicates from bootstrap-family generators;
short-window duplicates;
raw block reuse diagnostics;
duplicates measured after deterministic feature recomputation.
```

### 11.2 Decision on `regime_residual_bootstrap_v1`

`regime_residual_bootstrap_v1` should move to **v2 repair**, not be abandoned.

```text
Current decision: CONDITIONAL NO-GO FOR RL CONSUMPTION
Next action: decompose duplicate metrics and implement residual-jitter/reuse-cap/rejection-sampling mitigations
Potential after repair: strong P0/P1 augmentation baseline for ETHUSDT 4h SAC + tech_stat
```

### 11.3 Decision on `stationary_bootstrap_v1`

`stationary_bootstrap_v1` should remain a **negative/control baseline**, not a promoted augmentation generator, because it failed more severely on memorization. Its value is to prove that more sophisticated generators beat a simple dependency-preserving resampler.

### 11.4 Strategic conclusion

The correct standard is not “synthetic data must look statistically similar.” The correct standard is:

```text
Synthetic augmentation is allowed only if it is train-only, non-memorizing at the RL observation horizon, algebraically valid, stylized-fact preserving, cost-aware, and improves real validation robustness in paired comparisons against real-only and bootstrap baselines.
```

If `regime_residual_bootstrap_v2` can reduce dangerous full-window copies while preserving the current strong KS/Wasserstein/classifier/NN results, it should become the first Phase 4 candidate for ETHUSDT 4h. If it cannot, synthetic augmentation should remain a stress-testing tool rather than an RL training input.

---

## 12. Source links

### Project-specific context used

- Uploaded Project 3 Master Plan: data-centric RL trading research pipeline with distinct trading asset, simulation timeframe, and feature input concepts.
- Uploaded Phase 3 Overview: fixed PPO/SAC/DQN and systematic experiment design.
- Uploaded Phase 2 Overview and deliverables: trading features at 5m/15m/1h/4h and technical/statistical/decomposition/learned feature outputs.
- Uploaded feature sample: primitive OHLCV plus deterministic technical/statistical features.

### Research and technical references

1. Politis, D. N., & Romano, J. P. (1994). *The Stationary Bootstrap*.  
   https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf

2. Bollerslev, T. (1986). *Generalized Autoregressive Conditional Heteroskedasticity*.  
   https://public.econ.duke.edu/~boller/Published_Papers/joe_86.pdf

3. Hamilton, J. D. (1989). *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*.  
   https://www.ssc.wisc.edu/~bhansen/718/Hamilton1989.pdf

4. Cont, R. (2001). *Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues*.  
   https://www-stat.wharton.upenn.edu/~steele/Resources/FTSResources/StylizedFacts/Cont2001.pdf

5. Yoon, J., Jarrett, D., & van der Schaar, M. (2019). *Time-series Generative Adversarial Networks*.  
   https://papers.nips.cc/paper/8789-time-series-generative-adversarial-networks

6. Desai, A., Freeman, C., Wang, Z., & Beaver, I. (2021). *TimeVAE: A Variational Auto-Encoder for Multivariate Time Series Generation*.  
   https://arxiv.org/abs/2111.08095

7. Xu, T., Wenliang, L. K., Munn, M., & Acciaio, B. (2020). *COT-GAN: Generating Sequential Data via Causal Optimal Transport*.  
   https://arxiv.org/abs/2006.08571

8. Ni, H., et al. (2021). *Sig-Wasserstein GANs for Time Series Generation*.  
   https://arxiv.org/abs/2111.01207

9. Liao, S., et al. (2020/2023). *Conditional Sig-Wasserstein GANs for Time Series Generation*.  
   https://arxiv.org/abs/2006.05421

10. Yuan, X., & Qiao, Y. (2024). *Diffusion-TS: Interpretable Diffusion for General Time Series Generation*.  
    https://arxiv.org/abs/2403.01742

11. Huang, H., et al. (2024). *Generative Learning for Financial Time Series*.  
    https://proceedings.iclr.cc/paper_files/paper/2024/file/f90fc76b199fe6b0ec2a51aaf72c3277-Paper-Conference.pdf

12. Tanaka, Y., et al. (2025). *CoFinDiff: Controllable Financial Diffusion Model for Time Series Generation*.  
    https://arxiv.org/abs/2503.04164

13. Ericson, L., et al. (2024). *Deep Generative Modeling for Financial Time Series with Application in VaR: A Comparative Review*.  
    https://arxiv.org/abs/2401.10370

14. van den Burg, G. J. J., & Williams, C. K. I. (2021). *On Memorization in Probabilistic Deep Generative Models*.  
    https://proceedings.neurips.cc/paper_files/paper/2021/file/eae15aabaa768ae4a5993a8a4f4fa6e4-Paper.pdf

15. Synthetic Data Privacy Metrics (2025).  
    https://arxiv.org/html/2501.03941v1

16. Bailey, D. H., & López de Prado, M. (2014). *The Deflated Sharpe Ratio*.  
    https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf

17. Bailey, D. H., et al. (2015). *The Probability of Backtest Overfitting*.  
    https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
