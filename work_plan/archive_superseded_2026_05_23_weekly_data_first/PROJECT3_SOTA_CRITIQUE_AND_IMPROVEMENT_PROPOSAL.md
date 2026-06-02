# Project 3 SOTA Critique and Improvement Proposal for Orchestrator Agent

**Date:** 2026-05-02
**Prepared for:** Project 3 Tier 2 / Tier 1 orchestrator agents
**Prepared by:** Senior software/data-science review lane
**Format:** Markdown advisory document
**Scope:** Constructive critique and improvement suggestions for financial-trading data sources, preprocessing, feature engineering, model strategy, RL evaluation, and orchestration quality controls.
**Status:** Advisory and additive. This document does **not** invalidate completed work. It recommends guardrails and incremental modifications before or during Stage 3.1, with strict preservation of the existing held-out protocol.

---

## 0. Executive Summary for the Orchestrator

Project 3 is already architecturally strong. Its best decisions are: data-centric design, broad source acquisition, strict separation between traded asset and observation features, fixed RL algorithm configurations for Phase 3, staged screening/validation/held-out evaluation, point-in-time as-of alignment, and pre-registration before running experiments.

The main residual risk is **not lack of additional indicators**. The main residual risk is that a very large feature universe plus multiple assets, timeframes, seeds, and RL algorithms can produce convincing but non-reproducible results through leakage, stale macro data, revised economic data, low-frequency forward-fill artifacts, insufficient execution-cost realism, and multiple-testing pressure.

### 0.1 Recommended Orchestrator Decision

Adopt the following as an **additive pre-Stage-3.1 hardening package**:

| Priority | Recommendation | Orchestrator Action |
|---|---|---|
| P0 | Add a data availability and revision/vintage contract for every cross-source feature. | Require `event_time`, `available_at_utc`, `source_timestamp`, `vintage_or_revision_id`, `release_lag_policy`, and `staleness_age` metadata before Phase 3 consumption. |
| P0 | Add leakage sentinel tests. | Add negative controls, random-label tests, time-shift tests, post-cutoff feature audits, and train-only transformer/autoencoder/scaler validation. |
| P0 | Strengthen multiple-testing control beyond ranking by raw Sharpe. | Keep Deflated Sharpe Ratio; add Probability of Backtest Overfitting / CSCV and purged/embargoed validation where feasible. |
| P0 | Add execution-cost and slippage scenario matrix. | Evaluate every candidate under at least optimistic, base, and pessimistic cost assumptions. Reject candidates that only survive unrealistic frictions. |
| P1 | Change Stage A from “all combinations” to hierarchical feature-family ablation. | Rank source families before individual feature permutations. Use incremental marginal contribution and subscription value tests. |
| P1 | Add low-cost structural features supported by literature. | VRP, DVOL / crypto implied-volatility proxy, FX carry/momentum/value, funding term structure, jump-robust realized moments, and macro release-staleness features. |
| P1 | Add baseline models and null strategies. | No-trade, buy-and-hold, random policy, simple trend/momentum/reversal rules, and at least one supervised non-RL baseline. |
| P2 | Defer SOTA model lanes until RL baselines are reproducible. | Decision Transformer, CQL/IQL, time-series foundation-model embeddings, and TradingAgents overlay should become later lanes, not replacements for the pre-registered RL experiment. |

### 0.2 Highest-Value Critique

The current plan correctly treats Phase 3 as a data/feature evaluation rather than a hyperparameter-tuning exercise. The improvement is to make Phase 3 answer a sharper question:

> Which **data source families** and **feature-engineering families** add statistically defensible marginal value under realistic execution assumptions, after accounting for leakage, data revision, transaction costs, multiple testing, and regime instability?

This reframing preserves the project philosophy while reducing the risk that the best-looking candidate is merely the most overfit candidate.

---

## 1. Current Project Baseline Observed from Work Plan and Deliverables

### 1.1 Phase 3 Design Baseline

The current Phase 3 plan evaluates fixed Project 2 RL configurations over combinations of:

1. trading asset,
2. simulation timeframe,
3. feature input set,
4. feature engineering technique.

It explicitly holds RL algorithms fixed and varies the input data and feature representation. This is a strong experimental-control decision because it isolates the effect of data and features from the effect of repeated RL hyperparameter search.

Phase 3 also already requires:

- strict held-out discipline from `2025-01-01` onward,
- one final held-out evaluation per final candidate,
- pre-registration of experiment count, hypotheses, kill criteria, and multiple-testing correction,
- staged screening: Stage A quick screening, Stage B validation, Stage C held-out,
- subscription cancellation recommendations after marginal-value evaluation.

**Assessment:** This is a strong foundation. The suggested changes below should be treated as hardening, not replacement.

### 1.2 Data Acquisition Baseline

The current data lake already contains broad market, macro, alternative, reference, and economic-calendar data. The Stage 1.3 deliverable reports validated free-data acquisition across FRED, Yahoo Finance, commodities/ETFs/EM FX/bonds, HistData FX, Binance crypto, CoinMetrics Community, Blockchain.com, Etherscan snapshots, mempool.space, SEC EDGAR metadata, CFTC COT, FINRA short interest, DeFiLlama, calendars/holidays, economic-calendar actuals/proxies, BLS, BEA, Treasury, and OECD.

Known remaining gaps are not failures; they are subscription or credential decisions:

- advanced crypto on-chain history,
- historical ETH endpoint coverage,
- economic-calendar consensus/surprise data.

**Assessment:** The data acquisition phase is broad enough to support Stage A. The improvement should focus on **availability semantics, revision handling, and marginal-value measurement**, not indiscriminately adding paid sources.

### 1.3 Feature Engineering Baseline

The project already produced:

- multi-timeframe aligned trading-asset data for 50 assets at 5m, 15m, 1h, and 4h,
- 370 cross-source forward-filled files per timeframe using point-in-time backward/as-of merge and no interpolation,
- complete technical/statistical trading features,
- complete cross-source statistical features where numeric columns exist,
- complete wavelet, Hilbert, multitaper, EMD, and fractional-differentiation feature files,
- learned LSTM and CNN autoencoder embeddings for the active Stage A universe across BTC/USDT, ETH/USDT, BTCUSDT perpetual, EUR/USD, and USD/JPY at all four timeframes.

**Assessment:** Feature coverage is already extensive. The risk is now feature redundancy, hidden leakage, feature scaling leakage, autoencoder pretraining leakage, and overfitting through repeated candidate selection.

---

## 2. Constructive Critique

### 2.1 Strengths That Should Be Preserved

#### 2.1.1 Correct Experiment Philosophy

The plan correctly treats the project as a data-centric experiment rather than a model-hunting exercise. Fixing PPO, SAC, and DQN configurations during Phase 3 is methodologically sound because it makes the input-feature universe the primary independent variable.

#### 2.1.2 Proper Separation of Trading Asset and Observation Inputs

The work plan’s distinction between the traded asset/timeframe and cross-source feature inputs is essential. It prevents conflating the asset being traded with features used to represent market state.

#### 2.1.3 Point-in-Time As-Of Alignment

The Stage 2.1 deliverable states that cross-source alignment uses point-in-time backward/as-of merge and avoids interpolation. This is a major strength. The next improvement is to extend the same rigor from timestamp alignment to **economic availability and data revisions**.

#### 2.1.4 Staged Compute Discipline

The Stage A/B/C design is appropriate because the experiment space is too large for exhaustive full-budget RL runs.

#### 2.1.5 Built-In Subscription Accountability

The planned subscription cancellation review is a good data-governance mechanism. It should be made quantitative through marginal ablation, not only final-performance comparison.

---

### 2.2 Primary Risks

#### 2.2.1 Multiple-Testing and Feature-Search Inflation

A very large combination space creates a high probability that at least one configuration appears profitable by chance. Reinforcement learning amplifies this problem because stochastic training, reward design, and policy instability can act as additional implicit search dimensions.

**Risk consequence:** A policy may survive Stage A because it is lucky, not because its feature family has durable information.

**Corrective action:** Require Deflated Sharpe Ratio, PBO/CSCV-style overfitting assessment, seed variance reporting, and source-family ablations before declaring a feature family valuable.

#### 2.2.2 Availability Leakage in Macroeconomic and Alternative Data

Point-in-time timestamp alignment is necessary but not sufficient. Many macroeconomic series are revised after publication, and many data providers expose final revised values unless explicitly queried by vintage date. Economic-calendar actuals also have announcement-time and consensus-time semantics.

**Risk consequence:** A model may train on values that were not available when the trade decision would have been made.

**Corrective action:** Every cross-source feature should include an availability contract:

```text
feature_timestamp      = economic period or market event time
available_at_utc       = earliest timestamp at which this value was observable to the strategy
source_timestamp       = provider ingestion timestamp
vintage_or_revision_id = vintage date / revision date / provider snapshot id, if available
release_lag_policy     = explicit lag rule for non-real-time sources
staleness_age_bars     = number of simulation bars since the last source update
```

#### 2.2.3 Learned-Representation Leakage

Autoencoders, scalers, normalizers, PCA-like transforms, HMMs, and any learned preprocessing can leak future distribution information if fitted on the full series before train/validation/test splitting.

**Risk consequence:** The policy indirectly sees the held-out distribution through representation training or normalization statistics.

**Corrective action:** Require metadata proving that every fitted transform is trained only on the allowed training window for the experiment split. Stage C must not use any transform fitted with 2025 data.

#### 2.2.4 Forward-Filled Low-Frequency Data Staleness

Forward-filled macro, COT, on-chain, and economic-calendar features can be statistically valid but semantically stale. A value released days or weeks earlier has different meaning than a newly released value.

**Risk consequence:** The RL policy may interpret a stale macro value as current state rather than a stale state descriptor.

**Corrective action:** Add `age_since_last_update`, `bars_since_release`, and `source_is_stale` features per source family. These are low-cost and improve interpretability.

#### 2.2.5 Bar-Based Execution Optimism

At 5m and 15m, OHLCV-based backtests can materially overestimate tradability if spread, slippage, fees, order-size constraints, and partial fill risks are not represented.

**Risk consequence:** A high-turnover RL policy may look profitable in simulation but fail after costs.

**Corrective action:** Add cost scenarios and reject candidates that survive only under optimistic assumptions.

#### 2.2.6 Source-Family Attribution Ambiguity

If the best model uses “all features,” it may be impossible to tell whether performance came from macro, on-chain, decomposition, learned embeddings, or spurious interactions.

**Risk consequence:** The final report may not answer which data combinations actually matter.

**Corrective action:** Use hierarchical feature-family ablation and marginal contribution scoring.

---

## 3. Recommended Data Source and Data Type Enhancements

### 3.1 P0 — Real-Time/Vintage-Aware Macro Data Handling

#### 3.1.1 Recommendation

Before Phase 3 consumes macroeconomic features, require each macro feature to declare whether it uses:

- final revised data,
- real-time vintage data,
- delayed release-date proxy,
- synthetic surprise proxy,
- provider-supplied consensus/surprise.

For FRED series, prefer ALFRED/FRED vintage semantics wherever practical. The FRED API documents vintage dates as dates when series values were revised or newly released, and FRED observations can be queried with real-time parameters/vintage dates.

#### 3.1.2 Why It Matters

A model trained on final revised macro values can exploit information unavailable at decision time. This is one of the most dangerous non-obvious leakage modes in macro-driven trading systems.

#### 3.1.3 Orchestrator Acceptance Criteria

- Each macro feature file contains or references `available_at_utc`.
- Each macro feature file contains `vintage_policy` equal to one of:
  - `real_time_vintage`,
  - `release_lagged_actual`,
  - `final_revised_blocked_from_live_claims`,
  - `synthetic_proxy`.
- Final revised macro features are allowed only in explicitly labeled research lanes, not in live-tradability claims.
- Stage 3.1 design documents which macro policy each experiment uses.

#### 3.1.4 Research / Documentation Support

- FRED API documentation on series vintage dates: https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- FRED API documentation on observations and real-time date parameters: https://fred.stlouisfed.org/docs/api/fred/series_observations.html

---

### 3.2 P1 — Variance Risk Premium Features

#### 3.2.1 Recommendation

Add variance risk premium features as a low-cost risk-appetite / volatility-compensation feature family.

For equities:

```text
VRP_equity_t = implied_variance_t - realized_variance_t
```

where implied variance can be proxied from VIX and realized variance is computed from existing intraday returns.

For crypto:

```text
VRP_crypto_t = DVOL_implied_variance_t - realized_variance_crypto_t
```

where DVOL is available through Deribit’s volatility-index data endpoint.

#### 3.2.2 Why It Matters

Variance risk premium is a well-studied predictor/risk-compensation feature in financial markets. It is particularly suitable for RL observation spaces because it represents volatility regime, hedge demand, and risk appetite rather than a simple price indicator.

#### 3.2.3 Orchestrator Acceptance Criteria

- Add feature family `risk_premia/vrp`.
- Use only causal realized variance windows.
- Store implied-volatility source and availability timestamp.
- Include ablation group `risk_premia_only` and `base_plus_risk_premia` in Stage A.

#### 3.2.4 Research / Documentation Support

- Bollerslev, Tauchen, and Zhou, “Expected Stock Returns and Variance Risk Premia,” *Review of Financial Studies*, 2009: https://academic.oup.com/rfs/article/22/11/4463/1567695
- Deribit public volatility-index data documentation: https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data

---

### 3.3 P1 — FX Carry, Momentum, and Value Factors

#### 3.3.1 Recommendation

For G10 FX pairs, add explicit academic FX factor features:

```text
carry_base_quote_t = policy_rate_base_t - policy_rate_quote_t
momentum_12_1_t    = trailing 12-month return excluding most recent month
value_ppp_dev_t    = log(real_exchange_rate_t) - log(PPP_reference_t)
```

Where direct policy rates are not available at the same frequency, forward-fill with availability metadata and include staleness features.

#### 3.3.2 Why It Matters

FX returns have a large academic literature around carry, momentum, and value factors. Technical features alone can miss these structural drivers.

#### 3.3.3 Orchestrator Acceptance Criteria

- Add feature family `fx_factors`.
- Include only for FX assets and cross-FX context features.
- Validate currency mapping direction carefully: base-minus-quote vs quote-minus-base must be consistent with pair definition.
- Add unit tests for EUR/USD and USD/JPY sign conventions.

#### 3.3.4 Research Support

- Lustig, Roussanov, and Verdelhan, “Common Risk Factors in Currency Markets,” *Review of Financial Studies*, 2011: https://doi.org/10.1093/rfs/hhr068
- Menkhoff, Sarno, Schmeling, and Schrimpf, “Currency Momentum Strategies,” *Journal of Financial Economics*, 2012: https://doi.org/10.1016/j.jfineco.2012.06.009
- Asness, Moskowitz, and Pedersen, “Value and Momentum Everywhere,” *Journal of Finance*, 2013: https://doi.org/10.1111/jofi.12021

---

### 3.4 P1 — Crypto Funding-Rate Term Structure and Perpetual Basis

#### 3.4.1 Recommendation

Promote funding-rate features from “alternative add-on” to a first-class crypto/perpetual feature family.

Suggested features:

```text
funding_rate_current
funding_rate_ma_3d
funding_rate_ma_7d
funding_rate_ma_30d
funding_rate_zscore_30d
funding_rate_cumulative_7d
spot_perp_basis
basis_zscore_30d
basis_momentum_7d
```

#### 3.4.2 Why It Matters

Crypto returns are influenced by market-specific factors such as momentum, investor attention, network activity, and derivatives market structure. Funding and basis describe leverage demand and crowded positioning in perpetual markets.

#### 3.4.3 Orchestrator Acceptance Criteria

- Add ablation group `crypto_derivatives_structure`.
- Include only for crypto/perpetual candidates or as cross-source context.
- Validate funding timestamps exactly; funding intervals are not equivalent to bar timestamps.
- Add `bars_until_next_funding` and `bars_since_last_funding`.

#### 3.4.4 Research Support

- Liu and Tsyvinski, “Risks and Returns of Cryptocurrency,” *Review of Financial Studies*, 2021: https://doi.org/10.1093/rfs/hhaa113
- Liu, Tsyvinski, and Wu, “Common Risk Factors in Cryptocurrency,” NBER working paper: https://www.nber.org/papers/w25882

---

### 3.5 P2 — Limit Order Book and Microstructure Features

#### 3.5.1 Recommendation

Add order-book features only under a clearly labeled live/recent-data lane, unless paid historical LOB data is later justified by Stage A evidence.

Suggested live snapshot features:

```text
best_bid
best_ask
mid_price
spread_bps
weighted_mid
top5_bid_depth
top5_ask_depth
order_book_imbalance_top5
order_book_imbalance_top20
microprice
```

#### 3.5.2 Why It Matters

Order-flow imbalance and depth can explain short-horizon price impact. However, free historical LOB snapshots are generally unavailable, and adding live-only data can break comparability with historical backtests.

#### 3.5.3 Orchestrator Acceptance Criteria

- Do not mix live-only LOB features into historical Stage A experiments unless historical coverage is explicitly available.
- Store raw snapshot provenance or derived feature provenance.
- Never backfill synthetic LOB from OHLCV.
- Treat LOB as a future live/recent experiment lane.

#### 3.5.4 Research / Documentation Support

- Cont, Kukanov, and Stoikov, “The Price Impact of Order Book Events,” *Journal of Financial Econometrics*, 2014: https://academic.oup.com/jfec/article/12/1/47/816163
- Binance Spot API market data endpoint `/api/v3/depth`: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Zhang, Zohren, and Roberts, “DeepLOB: Deep Convolutional Neural Networks for Limit Order Books,” 2018/2019: https://arxiv.org/abs/1808.03668

---

### 3.6 P2 — Economic Surprise Features

#### 3.6.1 Recommendation

Treat economic surprise as a conditional subscription decision. If no consensus data is available, use z-scored release actuals only as a **proxy**, not as a true surprise index.

Suggested proxy features:

```text
release_actual_zscore
release_actual_change_zscore
release_category_recent_surprise_proxy_sum
bars_since_release
is_release_window
```

#### 3.6.2 Why It Matters

True economic surprise is the difference between actual and expected releases. Actual-only z-scores can represent macro shocks, but they are not equivalent to market surprise because market expectations are omitted.

#### 3.6.3 Orchestrator Acceptance Criteria

- Label actual-only features as `surprise_proxy`, not `surprise`.
- If Trading Economics, FXStreet, Bloomberg-like, or other consensus source is added, isolate it in a paid-source ablation family.
- Add a subscription-value test: `macro_actuals_proxy` versus `macro_consensus_surprise`.

#### 3.6.4 Research Support

- Scotti, “Surprise and Uncertainty Indexes,” *Journal of International Economics*, 2016: https://doi.org/10.1016/j.jinteco.2016.03.002
- Levich, “FX Surprises,” NBER Working Paper, 2012: https://www.nber.org/papers/w17849

---

## 4. Recommended Preprocessing and Feature Engineering Enhancements

### 4.1 P0 — Fitted-Transform Leakage Audit

#### 4.1.1 Recommendation

Before Stage 3.1 consumes features, audit all fitted transforms:

- scalers,
- rolling normalizers,
- PCA-like transforms,
- autoencoders,
- HMM regime models,
- feature-selection models,
- imputation policies,
- fractional differentiation parameter selection,
- learned embeddings.

#### 4.1.2 Required Metadata

Every fitted transform should have a metadata artifact containing:

```yaml
transform_id: string
feature_family: string
fit_start_timestamp: timestamp
fit_end_timestamp: timestamp
fit_assets: list
fit_timeframes: list
fit_columns: list
fit_excludes_heldout_2025: true|false
fit_excludes_validation_if_required: true|false
random_seed: int|null
software_version: string
input_manifest_hash: string
output_manifest_hash: string
```

#### 4.1.3 Acceptance Criteria

- No Stage C candidate may consume transforms fitted on 2025 data.
- No Stage B candidate may consume transforms fitted on Stage B validation data unless the experiment design explicitly permits transductive unsupervised fitting and labels it as non-live-equivalent.
- Any violation is a blocker, not a warning.

---

### 4.2 P1 — Jump-Robust Realized Volatility and Jump Features

#### 4.2.1 Recommendation

Add jump-robust realized-volatility features:

```text
realized_variance
bipower_variation
tripower_variation
jump_variation = max(realized_variance - bipower_variation, 0)
jump_intensity
jump_signed_sum
```

#### 4.2.2 Why It Matters

Standard realized variance mixes continuous volatility and jumps. Bipower variation provides a jump-robust estimate of continuous variation, while the difference between realized variance and bipower variation can represent jumps.

#### 4.2.3 Acceptance Criteria

- Use causal rolling windows only.
- Compute from existing intraday bars.
- Include in ablation group `realized_moments_jump_robust`.
- Store window length and bar source.

#### 4.2.4 Research Support

- Barndorff-Nielsen and Shephard, “Power and Bipower Variation with Stochastic Volatility and Jumps,” *Journal of Financial Econometrics*, 2004: https://doi.org/10.1093/jjfinec/nbh001
- Andersen, Bollerslev, and Diebold, “Roughing It Up: Including Jump Components in the Measurement, Modeling, and Forecasting of Return Volatility,” *Review of Economics and Statistics*, 2007: https://doi.org/10.1162/rest.89.4.701

---

### 4.3 P1 — Microstructure-Noise-Robust Volatility for 5m/15m

#### 4.3.1 Recommendation

For 5m/15m experiments, add a volatility-estimation robustness lane using two-scale or subsampling-inspired realized volatility.

#### 4.3.2 Why It Matters

Even at 5m, microstructure noise, bid/ask bounce, and exchange-specific artifacts can contaminate realized volatility. Robust estimators reduce false volatility signals.

#### 4.3.3 Acceptance Criteria

- Add only if computation is cheap relative to current feature-generation load.
- Do not extend to 1m; the master plan explicitly excludes 1m.
- Compare against standard realized variance in Stage A ablation.

#### 4.3.4 Research Support

- Zhang, Mykland, and Aït-Sahalia, “A Tale of Two Time Scales: Determining Integrated Volatility with Noisy High-Frequency Data,” *Journal of the American Statistical Association*, 2005: https://doi.org/10.1198/016214504000000817

---

### 4.4 P1 — Regime Features and Regime-Aware Normalization

#### 4.4.1 Recommendation

Add HMM-derived regime labels as features and optionally evaluate regime-aware normalization. However, treat regime-aware normalization as a fitted transform requiring strict train-only fitting.

Suggested features:

```text
regime_low_vol_probability
regime_high_vol_probability
regime_crash_probability
regime_entropy
bars_since_regime_change
```

#### 4.4.2 Why It Matters

Financial time series are non-stationary. Regime labels can help an RL policy distinguish trend, high-volatility, crash, and quiet regimes. Regime probabilities are often safer than hard labels because they preserve uncertainty.

#### 4.4.3 Acceptance Criteria

- HMM fitting must exclude held-out data.
- Store model metadata and fit window.
- Evaluate as a feature family first; do not globally normalize all features by regime before proving no leakage.

#### 4.4.4 Research Support

- Hamilton, “A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle,” *Econometrica*, 1989: https://doi.org/10.2307/1912559

---

### 4.5 P2 — Causal Discovery / PCMCI+ as an Audit Lane, Not a Primary Selector

#### 4.5.1 Recommendation

Defer PCMCI+ or related causal-discovery feature selection until the Stage 3 framework can guarantee no leakage. Use it first as a diagnostic report, not as a feature selector that influences held-out evaluation.

#### 4.5.2 Why It Matters

Causal discovery can reduce spurious correlation, but it is computationally expensive and easy to misuse in time-series finance. If run on too much data or after examining validation outcomes, it becomes a selection-leakage mechanism.

#### 4.5.3 Acceptance Criteria

- Run only on training split.
- Pre-register lags, variables, independence tests, and selection thresholds.
- Produce a report artifact.
- Do not change Stage C candidates after seeing Stage C results.

#### 4.5.4 Research Support

- Runge et al., “Detecting and Quantifying Causal Associations in Large Nonlinear Time Series Datasets,” *Science Advances*, 2019: https://www.science.org/doi/10.1126/sciadv.aau4996
- Runge, “Discovering Contemporaneous and Lagged Causal Relations in Autocorrelated Nonlinear Time Series Datasets,” UAI 2020: https://proceedings.mlr.press/v124/runge20a.html
- Tigramite documentation: https://jakobrunge.github.io/tigramite/

---

## 5. Recommended Experiment and Evaluation Enhancements

### 5.1 P0 — Null Strategies and Baseline Models

#### 5.1.1 Recommendation

Add baseline strategies to every Stage A/B/C report:

```text
no_trade
buy_and_hold
random_policy_same_turnover
simple_momentum_rule
simple_mean_reversion_rule
volatility_targeted_buy_and_hold
supervised_tree_or_linear_baseline
```

#### 5.1.2 Why It Matters

An RL strategy is not valuable merely because it has positive returns. It is valuable only if it improves risk-adjusted returns after costs against simple alternatives.

#### 5.1.3 Acceptance Criteria

- Every RL candidate must be compared to baselines under identical data split and cost model.
- Random policy should be turnover-matched where possible.
- A candidate cannot be promoted if it underperforms a simple baseline after costs unless the report explains why.

---

### 5.2 P0 — Deflated Sharpe Ratio and Probability of Backtest Overfitting

#### 5.2.1 Recommendation

Keep Deflated Sharpe Ratio and add PBO/CSCV-style analysis where feasible.

#### 5.2.2 Why It Matters

Sharpe ratios are biased upward when many strategies are tested. Deflated Sharpe Ratio corrects for selection bias, non-normality, and multiple testing. PBO/CSCV estimates the probability that the selected strategy is overfit.

#### 5.2.3 Acceptance Criteria

- Stage A report includes raw Sharpe, DSR, seed mean/std, and turnover-adjusted metrics.
- Stage B includes PBO/CSCV-style diagnostic if implementation is feasible.
- Final report clearly distinguishes raw performance from deflated/multiple-testing-adjusted evidence.

#### 5.2.4 Research Support

- Bailey and López de Prado, “The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality,” 2014: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey et al., “The Probability of Backtest Overfitting,” 2015: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

---

### 5.3 P0 — Cost, Slippage, and Turnover Scenario Matrix

#### 5.3.1 Recommendation

Evaluate every candidate under a minimum three-scenario transaction-cost model:

```text
cost_scenario_optimistic
cost_scenario_base
cost_scenario_pessimistic
```

Each scenario should include:

```text
fee_bps
spread_bps
slippage_bps_or_volume_function
minimum_order_notional
turnover_penalty
funding_cost_for_perpetuals
borrow_or_financing_cost_if_applicable
```

#### 5.3.2 Why It Matters

High-turnover RL policies often exploit simulator friction gaps. A policy that survives only under optimistic costs should not be promoted to held-out testing.

#### 5.3.3 Acceptance Criteria

- Stage A can use simplified costs but must not use zero costs for promotion decisions.
- Stage B must use realistic base and pessimistic costs.
- Stage C result must report performance under all three scenarios.

---

### 5.4 P1 — Hierarchical Feature-Family Ablation

#### 5.4.1 Recommendation

Stage A should not begin with arbitrary combinations of all features. Use a hierarchical design:

1. Base OHLCV / returns / volatility.
2. Base + technical/statistical.
3. Base + decomposition.
4. Base + learned embeddings.
5. Base + macro/risk factors.
6. Base + crypto on-chain/funding for crypto assets.
7. Base + FX factors for FX assets.
8. Best pairs of feature families.
9. All features only after family-level evidence.

#### 5.4.2 Why It Matters

The final report’s goal is data-source and feature-technique ranking. That requires marginal attribution. A giant all-feature policy cannot provide clean attribution.

#### 5.4.3 Acceptance Criteria

- Every feature family has a defined ablation ID.
- Stage A report ranks feature families by incremental value over base.
- Paid-source features are evaluated both alone and as incremental additions to free features.
- Subscriptions are judged by marginal contribution, not by whether the final all-feature model used them.

---

### 5.5 P1 — Regime-Sliced Evaluation

#### 5.5.1 Recommendation

Report performance by market regime:

```text
low_volatility
high_volatility
trend_up
trend_down
range_bound
crash_or_stress
high_funding
low_funding
high_macro_event_density
```

#### 5.5.2 Why It Matters

A strategy that performs well overall may fail catastrophically in specific regimes. Regime slicing makes failure modes visible and allows the orchestrator to identify where data families help.

#### 5.5.3 Acceptance Criteria

- Stage B report includes regime-sliced returns, drawdown, turnover, and action distribution.
- Candidates with unstable regime behavior require explicit risk notes before Stage C.

---

## 6. Recommended Model Strategy Enhancements

### 6.1 P0 — Keep PPO/SAC/DQN Fixed for Core Phase 3

#### 6.1.1 Recommendation

Do not replace the current core Phase 3 model plan. Fixed PPO, SAC, and DQN configurations remain appropriate for isolating data/feature value.

#### 6.1.2 Why It Matters

Changing algorithms during data-source evaluation would confound the experiment. The current design correctly isolates the data/feature axis.

---

### 6.2 P1 — Add Supervised Forecasting Baselines as Diagnostics, Not Replacement

#### 6.2.1 Recommendation

Add at least one non-RL supervised baseline to estimate whether the feature set contains predictive information before RL consumes it.

Possible baselines:

```text
regularized logistic/linear model for direction or return
LightGBM/XGBoost-style tree model if available
simple MLP or temporal CNN if already implemented
```

#### 6.2.2 Why It Matters

If a feature family has no predictive or state-discriminative value under simple models, RL may still exploit it through reward shaping, but the orchestrator should know that the evidence is weaker.

#### 6.2.3 Acceptance Criteria

- Baselines use the same train/validation splits.
- Baselines are not optimized on held-out data.
- Feature family ranking includes both RL and non-RL diagnostic evidence.

---

### 6.3 P2 — Time-Series Foundation Models as Later Embedding Lanes

#### 6.3.1 Recommendation

After core Stage A/B baselines are stable, evaluate time-series foundation models as feature extractors, not as immediate replacements for RL policies.

Candidate families:

- Chronos,
- TimesFM,
- Lag-Llama,
- Time-MoE,
- PatchTST/iTransformer-style architectures for supervised baselines.

#### 6.3.2 Why It Matters

Recent time-series foundation models show strong zero-shot or transfer performance on forecasting benchmarks, but forecasting benchmark success does not automatically imply tradable alpha. They should be evaluated as embeddings or diagnostic forecasters under the same trading-cost and leakage controls.

#### 6.3.3 Acceptance Criteria

- Do not use 2025 data for fine-tuning or prompt calibration.
- Keep as a separate experimental lane.
- Compare embeddings against existing LSTM/CNN autoencoder embeddings.
- Require cost-adjusted trading evaluation, not just forecast loss.

#### 6.3.4 Research Support

- Ansari et al., “Chronos: Learning the Language of Time Series,” 2024: https://arxiv.org/abs/2403.07815
- Das et al., “A Decoder-Only Foundation Model for Time-Series Forecasting” / TimesFM, ICML 2024: https://proceedings.mlr.press/v235/das24a.html
- Rasul et al., “Lag-Llama: Towards Foundation Models for Probabilistic Time Series Forecasting,” 2023/2024: https://arxiv.org/abs/2310.08278
- Shi et al., “Time-MoE: Billion-Scale Time Series Foundation Models with Mixture of Experts,” 2024: https://arxiv.org/abs/2409.16040
- Nie et al., “A Time Series is Worth 64 Words: Long-term Forecasting with Transformers,” PatchTST, 2022/2023: https://arxiv.org/abs/2211.14730
- Zeng et al., “Are Transformers Effective for Time Series Forecasting?”, 2022: https://arxiv.org/abs/2205.13504

---

### 6.4 P2 — Offline RL and Decision Transformer Lane After Reproducible Baselines

#### 6.4.1 Recommendation

Consider offline RL only after Stage 3.1 baselines are reproducible. Candidate methods:

- Conservative Q-Learning,
- Implicit Q-Learning,
- Decision Transformer.

#### 6.4.2 Why It Matters

Trading is naturally an offline-data-heavy domain. However, offline RL is sensitive to dataset coverage and can produce policies that choose actions outside the behavior distribution unless constrained. Conservative/offline methods are promising but should not disrupt the current data-evaluation experiment.

#### 6.4.3 Acceptance Criteria

- Create a separate `offline_rl_lane` after core baselines.
- Use behavior-policy diagnostics and action-coverage reports.
- Compare against the same cost model.
- Do not evaluate on held-out more than once.

#### 6.4.4 Research Support

- Kumar et al., “Conservative Q-Learning for Offline Reinforcement Learning,” NeurIPS 2020: https://proceedings.neurips.cc/paper/2020/hash/0d0fd7c6e093f7b804fa0150b875b868-Abstract.html
- Kostrikov, Nair, and Levine, “Offline Reinforcement Learning with Implicit Q-Learning,” 2021/2022: https://openreview.net/forum?id=68n2s9ZJWF8
- Chen et al., “Decision Transformer: Reinforcement Learning via Sequence Modeling,” NeurIPS 2021: https://arxiv.org/abs/2106.01345

---

### 6.5 P2 — TradingAgents as Overlay / Veto, Not Replacement

#### 6.5.1 Recommendation

Adopt TradingAgents only after Stage 3.1 produces baseline evidence packs. Use it as an explanation, critique, veto, or position-scaling overlay, not as a replacement for the pre-registered RL experiment.

#### 6.5.2 Suggested Evidence Pack

Each evidence pack should include:

```text
asset/timeframe/date range
RL signal and confidence
feature-family contributions
risk metrics
turnover and cost sensitivity
regime-sliced diagnostics
macro/on-chain/funding context
failure cases
```

#### 6.5.3 Acceptance Criteria

- Compare RL-only versus RL + TradingAgents veto/scaling on validation data.
- Do not allow LLM outputs to influence held-out candidate choice after held-out results are known.
- Require persistent decision logs.

#### 6.5.4 Research / Repository Support

- Xiao et al., “TradingAgents: Multi-Agents LLM Financial Trading Framework,” 2024/2025: https://arxiv.org/abs/2412.20138
- TradingAgents repository: https://github.com/TauricResearch/TradingAgents

---

## 7. Orchestrator-Ready Adoption Plan

### 7.1 Immediate Patch Set Before Stage 3.1

```yaml
patch_set: project3_stage31_sota_hardening
priority: P0
should_block_stage31_if_missing: true
items:
  - id: P0_001_feature_availability_contract
    target: features_manifest_and_cross_source_metadata
    action: require event_time, available_at_utc, source_timestamp, vintage_or_revision_id, release_lag_policy, staleness_age
    blocker_if_missing: true

  - id: P0_002_fitted_transform_leakage_audit
    target: scalers_autoencoders_hmm_feature_selection
    action: verify fit windows exclude heldout and validation where required
    blocker_if_2025_fit_detected: true

  - id: P0_003_cost_scenario_matrix
    target: experiment_design
    action: define optimistic/base/pessimistic fees, spread, slippage, funding, turnover penalty
    blocker_if_zero_cost_only: true

  - id: P0_004_null_and_baseline_strategies
    target: experiment_framework
    action: add no_trade, buy_hold, random_turnover_matched, simple_momentum, simple_reversal, supervised_baseline
    blocker_if_missing_from_stage_b: true

  - id: P0_005_multiple_testing_report
    target: experiment_metrics
    action: keep DSR, add PBO/CSCV diagnostic if feasible, always report seed variance and number_of_trials
    blocker_if_raw_sharpe_only: true
```

### 7.2 Stage A Feature-Family Matrix

```yaml
stage_a_feature_family_matrix:
  base:
    includes: [returns, OHLCV-derived causal basic statistics]
  technical_statistical:
    includes: [technical.parquet, statistical.parquet]
  decomposition:
    includes: [wavelet, hilbert, multitaper, emd, fracdiff]
  learned_embeddings:
    includes: [learned_lstm, learned_cnn]
  macro_risk:
    includes: [FRED, yield_curves, VIX/VRP, economic_release_proxy]
  crypto_structure:
    includes: [funding_rate, basis, onchain, defi, mempool]
    eligible_assets: [crypto, perpetuals]
  fx_structure:
    includes: [carry, momentum, value, COT]
    eligible_assets: [FX]
  cross_asset_context:
    includes: [equity_indices, commodities, bonds, ETFs, EM_FX]
  all_free_features:
    includes: [all validated free features]
  paid_or_subscription_features:
    includes: [only if acquired and separately tagged]
```

### 7.3 Promotion Rules

```yaml
promotion_rules:
  stage_a_to_stage_b:
    require:
      - positive net performance under base cost scenario
      - not dominated by simple baseline
      - seed_std_within_reasonable_bounds
      - no leakage audit failures
      - feature_family_delta_positive_or_explainable
    reject_if:
      - only profitable under zero_or_optimistic_cost
      - high turnover with fragile net returns
      - missing availability metadata
      - raw_sharpe_positive_but_dsr_unconvincing

  stage_b_to_stage_c:
    require:
      - robust under pessimistic cost scenario or explicit risk exception
      - survives multiple_testing_adjustment
      - regime_sliced_failure_modes_documented
      - no post_stage_b_feature_or_hyperparameter_changes
      - final candidate list frozen before heldout

  stage_c_final:
    require:
      - one deterministic heldout evaluation only
      - final report includes failures, not only winners
      - subscription value ranking uses marginal contribution
```

---

## 8. Suggested New Artifacts

### 8.1 `features/AVAILABILITY_CONTRACT.md`

Purpose: Explain event time, availability time, vintage time, and staleness semantics for every source family.

Required sections:

```text
source_family
native_frequency
event_time_definition
available_at_utc_definition
revision_policy
forward_fill_policy
staleness_feature_policy
known_limitations
```

### 8.2 `experiments/design/leakage_audit.md`

Purpose: Pre-Stage-3.1 leakage-control checklist.

Required tests:

```text
heldout_timestamp_exclusion
transform_fit_window_check
scaler_fit_window_check
autoencoder_fit_window_check
macro_vintage_check
forward_fill_availability_check
negative_control_random_label_check
feature_time_shift_sanity_check
```

### 8.3 `experiments/design/cost_model.md`

Purpose: Define cost assumptions consistently.

Required fields:

```text
asset_class
exchange_or_market
fee_bps
spread_bps
slippage_model
funding_model
borrow_model
min_trade_size
max_position_size
turnover_penalty
```

### 8.4 `experiments/design/feature_family_ablation_plan.md`

Purpose: Ensure Stage A answers source-family value, not just all-feature performance.

Required fields:

```text
feature_family_id
included_files
eligible_assets
eligible_timeframes
expected_hypothesis
promotion_metric
subscription_mapping_if_any
```

---

## 9. Subscription Decision Framework

### 9.1 Principle

Do not buy more data simply because it is available. Buy or retain paid data only if it produces measurable marginal value under the same evaluation protocol.

### 9.2 Recommended Subscription Tests

```yaml
subscription_value_tests:
  advanced_onchain:
    compare:
      - free_crypto_features
      - free_crypto_features_plus_advanced_onchain
    decision_metric: marginal_dsr_and_drawdown_improvement

  economic_consensus_surprise:
    compare:
      - macro_actuals_proxy
      - true_consensus_surprise
    decision_metric: marginal_value_for_fx_and_index_context

  historical_lob:
    compare:
      - OHLCV_microstructure_proxy
      - historical_lob_features
    decision_metric: short_timeframe_net_performance_after_costs
```

### 9.3 Cancellation Rule

A paid source should be cancelled or deferred if:

```text
marginal net performance <= 0 after costs
or marginal DSR is not materially better
or improvement occurs only in Stage A but disappears in Stage B
or improvement depends on a single seed or single asset
or data cannot be made point-in-time safe
```

---

## 10. Technical Self-Audit and Limitations of This Review

### 10.1 What This Review Can Support

This review supports:

- strengthening the existing plan,
- adding leakage and availability controls,
- prioritizing data-source families,
- improving evaluation methodology,
- deferring expensive model lanes until evidence justifies them,
- improving orchestrator artifacts and acceptance criteria.

### 10.2 What This Review Cannot Prove

This review does **not** prove that any feature, paper, or model will generate profitable trading performance in this project’s universe. The cited literature supports why a feature or method is a reasonable candidate for controlled experimentation; it does not substitute for Project 3’s own Stage A/B/C evidence.

### 10.3 Main Residual Uncertainties

1. The detailed Stage 3.1 experiment framework was not included in the retrieved artifact set, so this document may duplicate some safeguards already present there.
2. Project 2’s exact best PPO/SAC/DQN hyperparameters were not reviewed here.
3. Autoencoder train/validation split metadata was not audited at code level.
4. Cost model assumptions were not visible in the provided summaries.
5. Paid-source feasibility depends on budget, provider reliability, and licensing constraints.
6. Time-series foundation models and LLM trading agents are current research directions but require strict empirical validation before operational adoption.

### 10.4 Recommended Conservative Interpretation

Treat every SOTA addition as a **hypothesis to test**, not an upgrade by default. The highest-confidence improvements are methodological safeguards: availability metadata, transform-fit audits, realistic costs, multiple-testing control, and feature-family ablation.

---

## 11. References and Source Links

### 11.1 Project Artifacts Reviewed

- `00_PROJECT_3_MASTER_PLAN.md`
- `10_PHASE_1_OVERVIEW.md`
- `20_PHASE_2_OVERVIEW.md`
- `30_PHASE_3_OVERVIEW.md`
- `01_AGENT_INFRASTRUCTURE.md`
- `STAGE_1.3_DELIVERABLE.md`
- `STAGE_2.1_DELIVERABLE.md`
- `STAGE_2.2_DELIVERABLE.md`
- `STAGE_2.3_DELIVERABLE.md`
- `STAGE_2.4_DELIVERABLE.md`
- `INVENTORY.md`
- `SOTA_IMPROVEMENT_SUGGESTIONS.md`
- `SOTA_INTEGRATION_DECISIONS.md`
- `TRADINGAGENTS_INTEGRATION_ASSESSMENT.md`

### 11.2 Data Sources, Factors, and Market Microstructure

- Bollerslev, Tauchen, and Zhou, “Expected Stock Returns and Variance Risk Premia,” *Review of Financial Studies*, 2009: https://academic.oup.com/rfs/article/22/11/4463/1567695
- Lustig, Roussanov, and Verdelhan, “Common Risk Factors in Currency Markets,” *Review of Financial Studies*, 2011: https://doi.org/10.1093/rfs/hhr068
- Menkhoff, Sarno, Schmeling, and Schrimpf, “Currency Momentum Strategies,” *Journal of Financial Economics*, 2012: https://doi.org/10.1016/j.jfineco.2012.06.009
- Asness, Moskowitz, and Pedersen, “Value and Momentum Everywhere,” *Journal of Finance*, 2013: https://doi.org/10.1111/jofi.12021
- Liu and Tsyvinski, “Risks and Returns of Cryptocurrency,” *Review of Financial Studies*, 2021: https://doi.org/10.1093/rfs/hhaa113
- Liu, Tsyvinski, and Wu, “Common Risk Factors in Cryptocurrency,” NBER: https://www.nber.org/papers/w25882
- Scotti, “Surprise and Uncertainty Indexes,” *Journal of International Economics*, 2016: https://doi.org/10.1016/j.jinteco.2016.03.002
- Levich, “FX Surprises,” NBER Working Paper, 2012: https://www.nber.org/papers/w17849
- Cont, Kukanov, and Stoikov, “The Price Impact of Order Book Events,” *Journal of Financial Econometrics*, 2014: https://academic.oup.com/jfec/article/12/1/47/816163
- Zhang, Zohren, and Roberts, “DeepLOB: Deep Convolutional Neural Networks for Limit Order Books,” 2018/2019: https://arxiv.org/abs/1808.03668

### 11.3 Data Availability and Provider Documentation

- FRED API, vintage dates: https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- FRED API, series observations and real-time parameters: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- Deribit volatility index endpoint: https://docs.deribit.com/api-reference/market-data/public-get_volatility_index_data
- Binance Spot API market-data endpoints: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints

### 11.4 Preprocessing, Volatility, and Causality

- Barndorff-Nielsen and Shephard, “Power and Bipower Variation with Stochastic Volatility and Jumps,” *Journal of Financial Econometrics*, 2004: https://doi.org/10.1093/jjfinec/nbh001
- Andersen, Bollerslev, and Diebold, “Roughing It Up,” *Review of Economics and Statistics*, 2007: https://doi.org/10.1162/rest.89.4.701
- Zhang, Mykland, and Aït-Sahalia, “A Tale of Two Time Scales,” *Journal of the American Statistical Association*, 2005: https://doi.org/10.1198/016214504000000817
- Hamilton, “A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle,” *Econometrica*, 1989: https://doi.org/10.2307/1912559
- Runge et al., “Detecting and Quantifying Causal Associations in Large Nonlinear Time Series Datasets,” *Science Advances*, 2019: https://www.science.org/doi/10.1126/sciadv.aau4996
- Runge, “Discovering Contemporaneous and Lagged Causal Relations in Autocorrelated Nonlinear Time Series Datasets,” UAI 2020: https://proceedings.mlr.press/v124/runge20a.html

### 11.5 Backtesting, Multiple Testing, and RL Frameworks

- Bailey and López de Prado, “The Deflated Sharpe Ratio,” 2014: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey et al., “The Probability of Backtest Overfitting,” 2015: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Liu et al., “FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading in Quantitative Finance,” 2021: https://arxiv.org/abs/2011.09607
- Yang et al., “Qlib: An AI-oriented Quantitative Investment Platform,” 2020/2021: https://arxiv.org/abs/2009.11189
- Microsoft Qlib repository: https://github.com/microsoft/qlib

### 11.6 Modern Models and LLM Trading Agents

- Kumar et al., “Conservative Q-Learning for Offline Reinforcement Learning,” NeurIPS 2020: https://proceedings.neurips.cc/paper/2020/hash/0d0fd7c6e093f7b804fa0150b875b868-Abstract.html
- Kostrikov, Nair, and Levine, “Offline Reinforcement Learning with Implicit Q-Learning,” 2021/2022: https://openreview.net/forum?id=68n2s9ZJWF8
- Chen et al., “Decision Transformer: Reinforcement Learning via Sequence Modeling,” 2021: https://arxiv.org/abs/2106.01345
- Ansari et al., “Chronos: Learning the Language of Time Series,” 2024: https://arxiv.org/abs/2403.07815
- Das et al., “A Decoder-Only Foundation Model for Time-Series Forecasting,” ICML 2024: https://proceedings.mlr.press/v235/das24a.html
- Rasul et al., “Lag-Llama,” 2023/2024: https://arxiv.org/abs/2310.08278
- Shi et al., “Time-MoE,” 2024: https://arxiv.org/abs/2409.16040
- Nie et al., “PatchTST,” 2022/2023: https://arxiv.org/abs/2211.14730
- Zeng et al., “Are Transformers Effective for Time Series Forecasting?”, 2022: https://arxiv.org/abs/2205.13504
- Xiao et al., “TradingAgents: Multi-Agents LLM Financial Trading Framework,” 2024/2025: https://arxiv.org/abs/2412.20138
- TradingAgents repository: https://github.com/TauricResearch/TradingAgents

---

## 12. Final Orchestrator Instruction

The orchestrator should incorporate this document as an advisory improvement memo and create a bounded pre-Stage-3.1 hardening task. The task should **not** restart completed phases. It should add validation artifacts, leakage controls, cost-model documentation, feature-family ablation design, and prioritized low-cost feature additions. Model-expansion lanes should remain deferred until the core PPO/SAC/DQN feature-evaluation framework is reproducible and pre-registered.
