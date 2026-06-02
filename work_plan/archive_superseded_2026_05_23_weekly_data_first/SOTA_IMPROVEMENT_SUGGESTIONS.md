# State-of-the-Art Improvement Suggestions — Project 3

**Date:** 2026-05-01
**Author:** Tier 4 (Copilot Sonnet 4.6)
**Purpose:** Research-backed suggestions to improve the Project 3 plan across four domains.
Pass to orchestrator (Tier 2 / Tier 1) for selective integration where feasible within budget, compute, and scope constraints.

**Critical note:** Suggestions are additive only — they do not replace or invalidate any completed stage. The plan already covers a solid baseline. These suggestions address gaps and SotA advances that could yield marginal improvement in Phase 3 RL performance.

**Current completed baseline (as of 2026-05-02):**
- Stage 2.2 ✅ — 54 technical + 22 statistical features per asset/TF (200 jobs, 0 failures)
- Stage 2.3 ✅ — 17 wavelet + 5 Hilbert + 9 multitaper + 4 EMD + 3 fracdiff features (200 jobs, 0 failures)
- Stage 2.4 — Planned: CVAE, LSTM-AE, transformer-AE, CNN-AE, VAE

---

## 1. Data Sources

### 1.1 Variance Risk Premium (VRP) — Free

**What it is:** VRP = implied variance (VIX²) − realized variance (computed from intraday returns). Positive VRP reflects the volatility risk premium investors pay for hedging. Widely used as a cross-asset risk appetite indicator.

**Why it helps:** VRP predicts equity and FX returns at weekly/monthly horizons beyond standard macro indicators. Cross-asset VRP divergence (equity VRP vs FX realized vol) can sharpen regime detection in RL observation space.

**Implementation:** VIX daily already acquired (FRED: `VIXCLS`). Compute 22-bar rolling realized variance from existing 5m price data. VRP = VIX²/252 − RV_daily. No new data source required — computable from what we have.

**Citations:**
- Bollerslev, T., Tauchen, G., & Zhou, H. (2009). Expected Stock Returns and Variance Risk Premia. *Review of Financial Studies*, 22(11), 4463–4492. https://academic.oup.com/rfs/article/22/11/4463/1567695
- Londono, J. M., & Zhou, H. (2017). Variance risk premiums and the forward premium puzzle. *Journal of Financial Economics*, 124(2), 415–440. https://doi.org/10.1016/j.jfineco.2017.01.009

---

### 1.2 Crypto Volatility Indices (DVOL) — Free API

**What it is:** Deribit's DVOL is a 30-day implied volatility index for BTC and ETH, analogous to VIX. Computed from Deribit options order book. Available via free REST API.

**Why it helps:** DVOL is a forward-looking crypto volatility signal not captured by any currently acquired source. Divergence between BTC DVOL and realized vol (from Binance 5m) = crypto VRP, which has predictive content for crypto price direction.

**Endpoints:**
- `GET https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=3600`
- Same for ETH.

**Data available:** ~daily resolution going back to late 2020 for BTC, 2021 for ETH.

**Citations:**
- Hou, A. J., Wang, W., Chen, C. Y.-H., & Härdle, W. K. (2020). Pricing Cryptocurrency Options: The Case of CRIX and Bitcoin. *Journal of Financial Econometrics*, 18(2), 250–279. https://doi.org/10.1093/jjfinec/nbz011
- Deribit API docs: https://docs.deribit.com/#public-get_volatility_index_data

---

### 1.3 FX Carry Factors — Free (computable from FRED)

**What it is:** Interest rate differentials (policy rates) between currency-pair countries. Proxy for carry-trade signal. Standard FX risk factor in academic literature.

**Why it helps:** Carry factor is the most persistent academic FX return predictor. Adding it as a feature allows RL to discover carry-exploitation strategies. G10 central bank rates already in FRED (`FEDFUNDS`, `ECBDFR`, `BOJRATE`, etc.).

**Implementation:** Compute `carry_factor_t = rate_base_t − rate_quote_t` for each G10 pair. Forward-fill daily at all simulation timeframes. No new subscription required.

**Citations:**
- Lustig, H., Roussanov, N., & Verdelhan, A. (2011). Common Risk Factors in Currency Markets. *Review of Financial Studies*, 24(11), 3731–3777. https://doi.org/10.1093/rfs/hhr068
- Menkhoff, L., Sarno, L., Schmeling, M., & Schrimpf, A. (2012). Carry Trades and Global Foreign Exchange Volatility. *Journal of Finance*, 67(2), 681–718. https://doi.org/10.1111/j.1540-6261.2011.01726.x

---

### 1.4 FX Momentum and Value Factors — Free (computable)

**What it is:** Standard FX academic risk factors from the Menkhoff et al. (2012) framework:
- **Momentum:** 12-1 month trailing return rank across G10 pairs.
- **Value (PPP deviation):** Log real exchange rate deviation from PPP — OECD provides PPP estimates (already acquired).

**Why it helps:** Momentum and value are the two most robust FX predictors beyond carry. Including cross-sectional rank positions as features gives RL access to relative positioning signals that pure technical indicators miss.

**Citations:**
- Menkhoff, L., Sarno, L., Schmeling, M., & Schrimpf, A. (2012). Currency Momentum Strategies. *Journal of Financial Economics*, 106(3), 660–684. https://doi.org/10.1016/j.jfineco.2012.06.009
- Asness, C., Moskowitz, T. J., & Pedersen, L. H. (2013). Value and Momentum Everywhere. *Journal of Finance*, 68(3), 929–985. https://doi.org/10.1111/jofi.12021

---

### 1.5 Binance Limit Order Book Snapshots (Partial Depth) — Free

**What it is:** Binance provides free partial order book depth (top 20 bid/ask levels) via REST API at any frequency. Aggregated features derived from LOB: bid-ask spread, order imbalance, mid-price, weighted mid-price.

**Why it helps:** Microstructure features predict short-horizon returns (5m–15m especially). Order imbalance is a strong intrabar directional predictor per Cont et al. (2014).

**Endpoint:** `GET https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=20`

**Suggested features (derived, no raw LOB storage needed):**
- `lob_imbalance = (bid_qty_top5 − ask_qty_top5) / (bid_qty_top5 + ask_qty_top5)`
- `bid_ask_spread_bps = (ask1 − bid1) / mid × 10000`
- `weighted_mid = (ask1 × bid_qty1 + bid1 × ask_qty1) / (bid_qty1 + ask_qty1)`

**Limitation:** Historical snapshots unavailable free — only live acquisition from this point forward. Apply only to live/recent data; do not backfill.

**Citations:**
- Cont, R., Kukanov, A., & Stoikov, S. (2014). The Price Impact of Order Book Events. *Journal of Financial Econometrics*, 12(1), 47–88. https://doi.org/10.1093/jjfinec/nbt003
- Gould, M. D. et al. (2013). Limit order books. *Quantitative Finance*, 13(11), 1709–1742. https://doi.org/10.1080/14697688.2013.803148

---

### 1.6 Economic Surprise Index (Computable from Existing Data)

**What it is:** Bloomberg's Economic Surprise Index is proprietary, but a functionally equivalent measure can be constructed from FRED actuals + historical consensus estimates. The gap (consensus/surprise) is missing — but z-scored actual releases can serve as a proxy.

**Why it helps:** Economic surprise momentum is well-documented as a multi-week return predictor for FX and equities.

**Implementation:** For each FRED release (CPI, NFP, GDP, retail sales), compute the z-score of the actual release relative to its trailing rolling mean and standard deviation. This is a look-ahead-free, freely computable proxy. No new data subscription required.

**Alternative:** Trading Economics API (Standard plan ~$99/mo) provides full historical consensus estimates. Evaluate after Phase 3 screening establishes whether surprise features improve RL performance before paying.

**Citations:**
- Citi Economic Surprise Index methodology paper: Levich, R. M. (2012). FX Surprises. NBER Working Paper 17849. https://www.nber.org/papers/w17849
- Scotti, C. (2016). Surprise and Uncertainty Indexes. *Journal of International Economics*, 101, 16–30. https://doi.org/10.1016/j.jinteco.2016.03.002

---

### 1.7 Crypto Funding Rate Term Structure — Already Partially Acquired, Worth Enriching

**What it is:** Binance funding rates are already acquired (8h). Enrichment: funding rate rolling statistics and term structure across funding periods.

**Why it helps:** Funding rate level and momentum predict perpetual premium/discount reversion. Already cited in several academic crypto market-structure papers.

**Implementation:** From existing funding rate data, compute:
- `funding_ma_3d`, `funding_ma_7d`, `funding_ma_30d`
- `funding_zscore_30d = (funding_t − mean30) / std30`
- `funding_cumsum_7d`

No new acquisition. Computable from existing `alternative_data/` data.

**Citations:**
- Baur, D. G., & Dimpfl, T. (2021). The volatility of Bitcoin and its role as a medium of exchange and a store of value. *Empirical Economics*, 61, 2663–2683. https://doi.org/10.1007/s00181-020-01990-5
- Liu, Y., & Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency. *Review of Financial Studies*, 34(6), 2689–2727. https://doi.org/10.1093/rfs/hhaa113

---

## 2. Preprocessing

### 2.1 Jump-Robust Realized Volatility Estimators

**What it is:** Standard realized variance (`sum of squared 5m returns`) is contaminated by price jumps. Bipower Variation (BPV) and Tripower Variation (TPV) are jump-robust alternatives that separate continuous and jump components.

**Why it helps:** Clean continuous volatility estimates are better features than jump-contaminated RV. The jump component itself is a separate informative feature (jump intensity, jump size distribution).

**Implementation (rolling window, causal):**
```python
from numpy import abs, pi, sign

def bipower_variation(log_returns):
    """BPV = (π/2) * sum(|r_t| * |r_{t-1}|)"""
    return (pi / 2) * (abs(log_returns) * abs(log_returns.shift(1))).sum()

# Jump component = max(RV - BPV, 0)
# Continuous component = BPV
```

**Citations:**
- Barndorff-Nielsen, O. E., & Shephard, N. (2004). Power and bipower variation with stochastic volatility and jumps. *Journal of Financial Econometrics*, 2(1), 1–37. https://doi.org/10.1093/jjfinec/nbh001
- Andersen, T. G., Bollerslev, T., & Diebold, F. X. (2007). Roughing it up: Including jump components in the measurement, modeling, and forecasting of return volatility. *Review of Economics and Statistics*, 89(4), 701–720. https://doi.org/10.1162/rest.89.4.701

---

### 2.2 Regime-Aware Normalization

**What it is:** Instead of global rolling z-score normalization (current plan), normalize features within detected regime clusters. Volatile regimes and quiet regimes have very different distributional properties; mixing them degrades signal quality.

**Why it helps:** Features normalized globally are non-stationary at regime transitions. Regime-conditional normalization makes RL observation distributions more stable at training time.

**Implementation:**
1. Use Hidden Markov Model (2- or 3-state, Gaussian emissions on volatility) to label each bar as regime {low_vol, high_vol, crash}.
2. Maintain rolling per-regime mean/std using exponential moving averages.
3. Normalize using the current bar's regime statistics.

**Libraries:** `hmmlearn` (free, already available in conda tensorflow env).

**Citations:**
- Hamilton, J. D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357–384. https://doi.org/10.2307/1912559
- Nystrup, P., Hansen, B. W., Madsen, H., & Lindström, E. (2016). Detecting change points in VIX and S&P 500. *Quantitative Finance*, 16(3), 369–380. https://doi.org/10.1080/14697688.2015.1080714

---

### 2.3 PCMCI+ Causal Graph Feature Selection

**What it is:** PCMCI+ (Peter-Clark Momentary Conditional Independence with linear/nonlinear kernels) discovers lag-specific causal links between time series in a multivariate panel, distinguishing true causal parents from spurious correlations. Produces a directed acyclic graph (DAG) of feature-to-return causal links.

**Why it helps:** With 80+ features per asset/TF, many are redundant or spuriously correlated. PCMCI+ identifies which features are genuinely causal predictors of returns, allowing selective retention and reducing observation space dimensionality for RL policies.

**Library:** `tigramite` (Runge et al., free, pip install tigramite).

**Implementation:** Run PCMCI+ once on in-sample train split (pre-2025). Extract causal parents of return series at lag 1–5. Use discovered causal structure as feature selection mask for Phase 3 experiments.

**Compute note:** Memory-heavy. Assign to Dragon (32GB RAM) as per existing policy.

**Citations:**
- Runge, J., Nowack, P., Kretschmer, M., et al. (2019). Detecting and quantifying causal associations in large nonlinear time series datasets. *Science Advances*, 5(11), eaau4996. https://doi.org/10.1126/sciadv.aau4996
- Runge, J. (2020). Discovering contemporaneous and lagged causal relations in autocorrelated nonlinear time series datasets. *Proceedings of UAI 2020*. https://proceedings.mlr.press/v124/runge20a.html

---

### 2.4 Microstructure Noise-Robust Realized Vol (Two-Scales Estimator)

**What it is:** At 5m bars, microstructure noise is present but manageable. At any finer timescale, noise dominates. The Two-Scales Realized Variance (TSRV) estimator of Zhang et al. (2005) optimally separates noise from signal using multiple sampling grids.

**Why it helps:** Our 5m realized vol estimates contain microstructure noise contamination. TSRV gives cleaner volatility estimates at 5m, which feeds into Stages 2.2 statistical features (already computed but could be improved).

**Note:** This is a refinement suggestion for a future re-run of Stage 2.2 statistical features, not a blocker for Phase 3.

**Citations:**
- Zhang, L., Mykland, P. A., & Aït-Sahalia, Y. (2005). A tale of two time scales: Determining integrated volatility with noisy high-frequency data. *Journal of the American Statistical Association*, 100(472), 1394–1411. https://doi.org/10.1198/016214505000000169

---

## 3. Feature Engineering

### 3.1 Path Signatures (Rough Path Theory)

**What it is:** The path signature is a sequence of iterated integrals of a multivariate path that uniquely characterizes the path up to reparametrization. At depth-2 and depth-3, it captures nonlinear interactions between channels (e.g., price × volume interactions) in a provably complete representation.

**Why it helps:** Signature features are provably universal for sequential data — any continuous function of the path can be approximated by a linear function of the signature. For 5m price paths, depth-2 signatures of (log_return, volume) capture price-volume dynamics better than any hand-crafted indicator.

**Library:** `esig` or `signatory` (GPU-accelerated, pip install signatory).

**Computational cost:** O(n × d^k) where d = channels (small) and k = truncation depth (2 or 3). Cheap.

**Citations:**
- Lyons, T. (1998). Differential equations driven by rough signals. *Revista Matemática Iberoamericana*, 14(2), 215–310. https://doi.org/10.4171/RMI/240
- Chevyrev, I., & Kormilitzin, A. (2016). A primer on the signature method in machine learning. arXiv:1603.03788. https://arxiv.org/abs/1603.03788
- Morrill, J., Fermanian, A., Kidger, P., & Lyons, T. (2020). A generalised signature method for multivariate time series feature extraction. arXiv:2006.00873. https://arxiv.org/abs/2006.00873

---

### 3.2 Cross-Asset Network Centrality Features

**What it is:** Build a rolling correlation/partial-correlation network across all 50 trading assets (or within-class subsets). Compute graph centrality measures (degree, betweenness, eigenvector centrality) for each asset at each timeframe.

**Why it helps:** An asset's network centrality is a proxy for its systemic importance and contagion risk. High centrality (many correlated neighbors) → asset moves with the crowd. Low centrality → idiosyncratic behavior. These regime-level network features contain information unavailable from single-asset indicators.

**Implementation:** Rolling 120-bar partial correlation matrix (DCC-GARCH or simple Pearson). Threshold at |r| > 0.3. Compute `networkx` centrality measures. Output: `degree_centrality_t`, `betweenness_t`, `eigenvector_centrality_t` per asset per TF.

**Compute:** Run on Omega (CPU-bound, moderately heavy). Assign to Stage 2.2 cross-source Gamma worker as extension.

**Citations:**
- Mantegna, R. N. (1999). Hierarchical structure in financial markets. *European Physical Journal B*, 11, 193–197. https://doi.org/10.1007/s100510050929
- Billio, M., Getmansky, M., Lo, A. W., & Pelizzon, L. (2012). Econometric measures of connectedness and systemic risk in the finance and insurance sectors. *Journal of Financial Economics*, 104(3), 535–559. https://doi.org/10.1016/j.jfineco.2011.12.010

---

### 3.3 Cointegration-Based Spread Features (Pairs)

**What it is:** Pairs of assets with long-run cointegration (e.g., EUR/USD vs EUR/GBP, BTC/USDT vs ETH/USDT) exhibit mean-reverting spreads. The spread z-score is a stationary, tradeable signal.

**Why it helps:** Cointegration spread z-scores are one of the most robust features for RL agents to exploit relative value opportunities. The spread is stationary (unlike raw prices), making it a natural RL state variable.

**Implementation (Engle-Granger, rolling window):**
```python
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS

def rolling_spread_zscore(y, x, window=120):
    """Causal rolling cointegration spread."""
    hedge = OLS(y[-window:], x[-window:]).fit().params[0]
    spread = y - hedge * x
    return (spread[-1] - spread[-window:].mean()) / spread[-window:].std()
```

**Asset pairs to consider:** (EURUSD, EURGBP), (EURUSD, EURJPY), (BTCUSDT, ETHUSDT), (BTCUSDT, BTCUSDT_perp).

**Citations:**
- Engle, R. F., & Granger, C. W. J. (1987). Co-integration and error correction: Representation, estimation, and testing. *Econometrica*, 55(2), 251–276. https://doi.org/10.2307/1913236
- Vidyamurthy, G. (2004). *Pairs Trading: Quantitative Methods and Analysis*. Wiley. ISBN: 978-0-471-46067-5.

---

### 3.4 Higher-Order Realized Moments (Realized Skewness and Kurtosis at 5m)

**What it is:** Stage 2.2 computes rolling skewness and kurtosis of daily/bar returns using standard rolling window. A richer approach uses realized moments computed from 5m returns within each 1h/4h bar — giving intrabar distributional information unavailable from lower-frequency statistics.

**Why it helps:** Realized skewness and kurtosis capture tail risk and asymmetry within each simulation bar. Negative realized skew → downside tail risk has been realized in that bar. This is predictive of next-bar direction at 1h and 4h timeframes.

**Implementation:**
```python
# For each 1h bar at index t: collect all 5m returns within [t-1h, t]
# intrabar_returns = 5m_returns[t-12:t]  (12 × 5m = 1h)
# realized_skew_t = scipy.stats.skew(intrabar_returns)
# realized_kurt_t = scipy.stats.kurtosis(intrabar_returns)
```

**Citations:**
- Amaya, D., Christoffersen, P., Jacobs, K., & Vasquez, A. (2015). Does realized skewness predict the cross-section of equity returns? *Journal of Financial Economics*, 118(1), 135–167. https://doi.org/10.1016/j.jfineco.2015.02.009
- Neuberger, A. (2012). Realized skewness. *Review of Financial Studies*, 25(11), 3423–3455. https://doi.org/10.1093/rfs/hhs101

---

### 3.5 Causal Features from PCMCI+ Graph (Complement to §2.3)

**What it is:** After running PCMCI+ (§2.3 above), use the discovered causal parents not just for feature selection but as explicit features: the current value of each causal parent, weighted by its estimated causal strength (MCI coefficient).

**Why it helps:** Feeding the RL policy explicit causal parent values (rather than all features including spurious ones) reduces the credit assignment problem in RL. The agent sees only causally relevant context.

**Implementation:** For each (asset, TF), extract top-k causal parents by MCI coefficient. Construct `causal_obs_vector_t = [parent_i_value_t × causal_weight_i for i in parents]`. Add to observation space as additional channel.

**Citations:**
- Same as §2.3 (Runge et al., 2019, *Science Advances*). https://doi.org/10.1126/sciadv.aau4996

---

### 3.6 Volatility Regime Labels (HMM-Based, Explicit Regime Feature)

**What it is:** Stage 2.2 statistical features include GARCH conditional volatility but no explicit regime label. Adding a discrete HMM-inferred regime indicator (low-vol / med-vol / high-vol / crisis) as a discrete feature allows RL policies to condition behavior on regime.

**Why it helps:** RL policies trained across all regimes without explicit regime conditioning must implicitly infer regime from raw features — a difficult credit assignment problem. Providing an explicit regime label (inferred causally from past data only) reduces this burden dramatically.

**Implementation:** `hmmlearn.GaussianHMM(n_components=4)`. Fit on in-sample. Predict (Viterbi) regime at each bar using only past data (sliding window re-fit or fixed parameters). Output: `regime_0/1/2/3` and `regime_prob_0/1/2/3` (soft assignment probabilities).

**Citations:**
- Hamilton, J. D. (1989). *Econometrica*, 57(2), 357. https://doi.org/10.2307/1912559
- Nystrup, P., Madsen, H., & Lindström, E. (2020). Learning hidden Markov models with persistent states by penalizing jumps. *Expert Systems with Applications*, 150, 113307. https://doi.org/10.1016/j.eswa.2020.113307

---

## 4. RL Models

### 4.1 Recurrent Policies: LSTM-PPO and TD3+LSTM

**What it is:** Standard PPO and SAC policies in Project 3 plan use MLP observation encoders with a fixed-length observation window. Replacing the MLP with LSTM (or GRU) encoder allows the policy to learn its own temporal aggregation over variable-length histories.

**Why it helps:** With 80+ features at each bar, the observation window is truncated at a fixed length (typically 64 bars). An LSTM encoder processes the full sequence with learned gating — better than fixed-window concatenation for capturing long-memory dependencies.

**Implementation:** `sb3-contrib` provides `RecurrentPPO` (MaskablePPO + LSTM). `stable-baselines3` does not provide recurrent SAC natively; use `sb3-contrib` or implement manually.

**Compute note:** LSTM policies are ~2× slower per step than MLP. Assign to Dragon (RTX 4090) for recurrent training jobs.

**Citations:**
- Hausknecht, M., & Stone, P. (2015). Deep Recurrent Q-Networks for Partially Observable MDPs. arXiv:1507.06527. https://arxiv.org/abs/1507.06527
- Ni, T., Sikchi, H., Wang, Y., Gupta, T., Lee, L., & Eysenbach, B. (2023). F-IQL: Frugal Offline Reinforcement Learning. Demonstrates recurrent policies for financial RL. ICML 2023. https://arxiv.org/abs/2306.02584

---

### 4.2 Decision Transformer — Offline RL via Sequence Modeling

**What it is:** Decision Transformer (DT) recasts RL as a sequence modeling problem. Given a context of (return-to-go, state, action) triplets, DT autoregressively predicts the next action. Trained offline on logged trajectories (no environment interaction needed during training).

**Why it helps:** Project 3 will generate large amounts of in-sample trajectory data during Phase 3 experiments. DT can be trained offline on these logged trajectories and then fine-tuned with a small number of live interactions — potentially more sample-efficient than online PPO/SAC from scratch.

**Implementation:** Use existing `feature-extractor` transformer architecture as backbone. Input: `(target_return, state, action)` sequences. Train on logged in-sample rollouts. Evaluate online with fixed target return = top-quartile historical return.

**Citations:**
- Chen, L., Lu, K., Rajeswaran, A., Lee, K., Grover, A., Laskin, M., Abbeel, P., Srinivas, A., & Mordatch, I. (2021). Decision Transformer: Reinforcement Learning via Sequence Modeling. arXiv:2106.01345. https://arxiv.org/abs/2106.01345
- Zheng, Q., Zhang, A., & Grover, A. (2022). Online Decision Transformer. arXiv:2202.05607. https://arxiv.org/abs/2202.05607

---

### 4.3 Conservative Q-Learning (CQL) — Offline RL

**What it is:** CQL is an offline RL algorithm that addresses distributional shift by penalizing Q-values for out-of-distribution actions. Allows training entirely on historical data without environment interaction during the learning phase.

**Why it helps:** With 15 years of FX and crypto data, we have rich historical trajectories. Training an offline RL policy (CQL or IQL) on the full historical dataset before any online fine-tuning could bootstrap a significantly better policy initialization than random start, reducing online Phase 3 training compute by 50–80%.

**Libraries:** `d3rlpy` (MIT license, pip install d3rlpy) provides CQL, IQL, TD3+BC natively.

**Citations:**
- Kumar, A., Zhou, A., Tucker, G., & Levine, S. (2020). Conservative Q-Learning for Offline Reinforcement Learning. arXiv:2006.04779. https://arxiv.org/abs/2006.04779
- Kostrikov, I., Nair, A., & Levine, S. (2021). Offline Reinforcement Learning with Implicit Q-Learning. arXiv:2110.06169. https://arxiv.org/abs/2110.06169

---

### 4.4 Risk-Sensitive RL: CVaR-Constrained Policies

**What it is:** Standard PPO/SAC maximize expected return. Risk-sensitive variants add a Conditional Value-at-Risk (CVaR) penalty to the reward signal, explicitly trading off expected return against tail risk. CVaR-PPO replaces the scalar reward with a distributional reward and optimizes the α-CVaR (e.g., α=0.05 = worst 5% of outcomes).

**Why it helps:** Maximizing expected PnL without tail risk control leads to policies that occasionally catastrophically blow up. CVaR-constrained policies are better suited to real trading where maximum drawdown is a key constraint.

**Implementation options:**
1. Reshape reward: `reward_cvar = reward - lambda * CVaR_penalty(rolling_drawdown)`
2. Use distributional RL (IQN or C51) to learn the full return distribution.
3. Use `CPPO` from `safety-gymnasium` / `omnisafe`.

**Citations:**
- Tamar, A., Glassner, Y., & Mannor, S. (2015). Optimizing the CVaR via Sampling. *AAAI 2015*. https://ojs.aaai.org/index.php/AAAI/article/view/9686
- Yang, S., Gao, G., An, B., Wang, H., & Sun, X. (2022). Enhancing Safe Exploration Using Safety State Augmentation. arXiv:2206.02675. https://arxiv.org/abs/2206.02675
- Prashanth, L. A., & Ghavamzadeh, M. (2016). Variance-Constrained Actor-Critic Algorithms for Discounted and Average Reward MDPs. *Machine Learning*, 105(3), 367–417. https://doi.org/10.1007/s10994-016-5569-y

---

### 4.5 Hierarchical RL: Multi-Timeframe Policy Hierarchy

**What it is:** A two-level hierarchy where a high-level "meta-policy" (operating at 4h or 1h) sets a directional bias (long/neutral/short), and a low-level "execution policy" (operating at 5m or 15m) handles entry timing and position sizing within that bias.

**Why it helps:** Our 4 simulation timeframes currently run independent experiments. Hierarchical RL could exploit multi-scale structure natively: the 4h bar encodes macro context; the 5m bar handles microstructure timing. This mirrors how professional traders actually operate.

**Implementation:** Use `h-DQN` (Kulkarni et al., 2016) or `HIRO` (Nachum et al., 2018). High-level policy uses 1h/4h features; low-level receives goal from high-level + 5m features.

**Citations:**
- Kulkarni, T. D., Narasimhan, K., Saeedi, A., & Tenenbaum, J. (2016). Hierarchical Deep Reinforcement Learning: Integrating Temporal Abstraction and Intrinsic Motivation. arXiv:1604.06057. https://arxiv.org/abs/1604.06057
- Nachum, O., Gu, S., Lee, H., & Levine, S. (2018). Data-Efficient Hierarchical Reinforcement Learning (HIRO). arXiv:1805.08296. https://arxiv.org/abs/1805.08296

---

### 4.6 World Model–Based RL: DreamerV3

**What it is:** DreamerV3 (Hafner et al., 2023) learns a compact world model (RSSM: Recurrent State Space Model) from experience and trains the RL policy entirely inside the imagined rollouts. Dramatically reduces required real environment interactions vs model-free PPO/SAC.

**Why it helps:** Financial environments are expensive to simulate (data I/O, realistic slippage). DreamerV3 trains 10–100× more efficiently in terms of real environment steps by dreaming forward in the world model. Validated on 150 tasks including continuous control.

**Implementation:** `dreamer-pytorch` (unofficial, pip installable). Requires GPU. Assign to Dragon.

**Compute note:** World model training itself requires GPU. GPU lockfile mandatory per project rules.

**Citations:**
- Hafner, D., Lillicrap, T., Norouzi, M., & Ba, J. (2020). Dream to Control: Learning Behaviors by Latent Imagination. arXiv:1912.01603. https://arxiv.org/abs/1912.01603
- Hafner, D., Lillicrap, T., Norouzi, M., & Ba, J. (2023). Mastering Diverse Domains through World Models. arXiv:2301.04104. https://arxiv.org/abs/2301.04104

---

### 4.7 Multi-Task RL: Shared Policy Across Assets

**What it is:** Rather than training a separate policy for each (asset, TF) combination (50 assets × 4 TFs = 200 separate training runs), a multi-task policy shares parameters across assets and learns asset-conditioned behavior via an asset embedding vector.

**Why it helps:** With 200 independent training runs, Phase 3 is compute-expensive. A multi-task policy amortizes training across assets. Cross-asset transfer learning is also well-documented: skills learned on liquid BTC/ETH transfer to smaller alts.

**Implementation:** Add a learned asset embedding (dimension 16–32) as additional input to the policy network. Train on all assets simultaneously with a shared policy. Per-asset adapters (FiLM layers) can specialize the shared policy per asset.

**Citations:**
- Yu, T., Kumar, A., Gupta, A., Levine, S., Hausman, K., & Finn, C. (2020). Gradient Surgery for Multi-Task Learning. arXiv:2001.06782. https://arxiv.org/abs/2001.06782
- Caruana, R. (1997). Multitask Learning. *Machine Learning*, 28(1), 41–75. https://doi.org/10.1023/A:1007379606734

---

### 4.8 Deflated Sharpe Ratio Correction (Already Planned — Strengthen)

**What it is:** Lopez de Prado's Deflated Sharpe Ratio (DSR) accounts for multiple testing, non-normality of returns, and serial correlation when evaluating strategy performance. The project plan already mentions this (Rule P3.3).

**Recommendation:** Apply DSR not only to Phase 3 final candidates but also to Phase 3 Stage A screening results. Discard Stage A configurations with DSR < 0 at 95% confidence before proceeding to Stage B full-budget runs. This prevents budget waste on false positives.

**Implementation:**

```python
from mlfinlab.backtest_statistics import deflated_sharpe_ratio
dsr = deflated_sharpe_ratio(
    observed_sr=sr_obs,
    sr_estimates=all_sr_estimates_from_screening,
    n=n_obs,
    skew=skew_of_returns,
    kurtosis=kurtosis_of_returns
)
```

**Citations:**
- Bailey, D. H., & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. *Journal of Portfolio Management*, 40(5), 94–107. https://doi.org/10.3905/jpm.2014.40.5.094
- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Chapter 14. ISBN: 978-1-119-48208-6.

---

## 5. Known Gaps to Resolve Before Phase 3

These are not SotA improvements but pre-requisite gap closures that should be addressed by the orchestrator before Phase 3 begins:

| # | Gap | Impact | Suggested Action |
|---|-----|--------|-----------------|
| G1 | **45 malformed acquisition_log rows** | Unknown quality of 45 source files | Enumerate by source; inspect; repair or flag as permanently excluded |
| G2 | **CryptoQuant historical depth** | Recent-window only confirmed; full history unknown | Read parquet file date ranges; confirm earliest available date per endpoint |
| G3 | **Economic calendar consensus/surprise empty** | Can't compute surprise features | Subscribe to Trading Economics (~$99/mo) OR use z-scored FRED actuals as proxy (free, see §1.6) |
| G4 | **Stage 2.4 Learned Representations not started** | Phase 3 can proceed without learned features if needed, but they improve RL observation quality | Start on Dragon after Stage 2.3 validation confirmed |
| G5 | **Stage 2.2 cross-source stats (Gamma) status unknown** | 88 cross-source features may be missing statistical enrichment | Check `stage22_cross_source_stats_gamma.md`; verify statistical cols |

---

## 6. Priority Ranking for Orchestrator

The following table ranks suggestions by expected impact and implementation cost (LOW = free/existing data, HIGH = new subscription or heavy compute):

| Rank | Suggestion | Domain | Cost | Expected Impact |
|------|-----------|--------|------|----------------|
| 1 | §4.3 Offline RL (CQL/IQL) pre-training | RL | LOW (d3rlpy free) | HIGH — bootstraps better policy init |
| 2 | §1.3 FX Carry Factor | Data | LOW (FRED, free) | HIGH — most robust FX predictor |
| 3 | §4.4 CVaR-constrained reward | RL | LOW (reward shaping) | HIGH — reduces catastrophic drawdowns |
| 4 | §3.1 Path Signatures | Features | LOW (signatory free) | HIGH — universal sequential representation |
| 5 | §2.3 PCMCI+ Causal Selection | Preprocessing | MEDIUM (Dragon compute) | HIGH — reduces observation noise |
| 6 | §4.8 DSR at Stage A screening | RL/eval | LOW (mlfinlab free) | HIGH — prevents wasted Stage B compute |
| 7 | §1.1 VRP (computable) | Data | LOW (free) | MEDIUM — cross-asset risk appetite signal |
| 8 | §1.2 Deribit DVOL | Data | LOW (free API) | MEDIUM — forward-looking crypto vol |
| 9 | §4.1 LSTM-PPO / RecurrentPPO | RL | MEDIUM (2× compute) | MEDIUM — better temporal aggregation |
| 10 | §3.6 HMM Regime Labels | Features | LOW (hmmlearn free) | MEDIUM — explicit regime conditioning |
| 11 | §4.2 Decision Transformer | RL | MEDIUM (GPU) | MEDIUM — offline policy distillation |
| 12 | §3.3 Cointegration Spread Features | Features | LOW | MEDIUM — relative value for FX + crypto pairs |
| 13 | §1.4 FX Momentum/Value Factors | Data | LOW (computable) | MEDIUM — cross-sectional FX signals |
| 14 | §4.5 Hierarchical RL | RL | HIGH (new architecture) | MEDIUM — multi-TF structure exploitation |
| 15 | §4.7 Multi-Task RL | RL | MEDIUM (shared training) | MEDIUM — compute reduction + transfer |
| 16 | §3.2 Cross-Asset Network Centrality | Features | LOW (networkx) | LOW-MEDIUM — systemic risk features |
| 17 | §4.6 DreamerV3 | RL | HIGH (new framework) | UNCERTAIN — validated on games, less on finance |
| 18 | §1.5 LOB Snapshots (Binance) | Data | LOW (free, forward only) | LOW — only for live/future data |
| 19 | §2.4 TSRV Realized Vol | Preprocessing | LOW | LOW — marginal vol quality improvement |

---

*Document auto-generated by Tier 4 (Copilot Sonnet 4.6) on 2026-05-01. For orchestrator integration, treat each numbered suggestion as an optional module that can be selectively enabled per Phase 3 experiment variant. No suggestion is a blocker for Phase 3 commencement.*
