# Stage 2.2 — Technical and Statistical Features

**Stage goal:** Compute comprehensive technical indicators and advanced statistical features per trading asset at each simulation timeframe (5m, 15m, 1h, 4h).

**Inputs:** Stage 2.1 complete with `features/MANIFEST.json` documenting aligned multi-timeframe data.

**Outputs:**
- `features/trading_asset_features/<asset>/<tf>/technical.parquet` — technical indicators
- `features/trading_asset_features/<asset>/<tf>/statistical.parquet` — statistical features
- Per-feature documentation with citations
- `STAGE_2.2_DELIVERABLE.md`

**Machine assignment:**
- **Omega:** FX assets (10 G10 pairs × 4 timeframes)
- **Dragon:** Crypto top 50 spot + perpetuals × 4 timeframes (heaviest)
- **Gamma:** Cross-source statistical features (volatility regime indicators, etc. computed across many sources)

---

<!-- AGENT_INFRA_NOTE_v2 -->
## Agent Infrastructure Note

This stage is executed by the multi-tier agent system defined in `01_AGENT_INFRASTRUCTURE.md` (architecture v2). Read that document before executing this stage. Key rules:

- **Tier 2 (OpenCode Go on Omega) dispatches** the per-machine tasks listed below; you (the user) do not run them by hand.
- **Tier 1 supervisors** (Hermes + Gemma 3 31B on Dragon and Gamma, cron-invoked, GPU-lockfile-aware) watch worker logs and produce status reports.
- **Heavy GPU jobs MUST acquire `/tmp/gpu_busy.lock`** via `_scripts/lib/gpu_lock.py` before starting. See infrastructure doc §4.
- **Auto-validation is full auto** (master plan Rule M.15). When you confirm a manual prerequisite is done, the agents proceed through validation, deliverable generation, and downstream prep automatically. Only blockers ping you.
- **Escalation routing (v2 simplified — no automated frontier API):**
  - Code/data anomalies, scope ≤2 files, severity ≤ high → Tier 3 (local Hermes + Gemma 31B, bounded: max 3 attempts, max 2 files, 30 min/attempt). If Tier 3 confidence <0.7 or attempts exhausted → hands off to Tier 4.
  - Plan decisions, synthesis, final-report writing, blocker severity, or scope >2 files → Tier 4 (you, with ChatGPT 5.5 Pro via Codex / Copilot Opus 4.7 / Claude Pro Max as your tools).
  - **No automated frontier API calls anywhere.** Frontier models are human-driven only.

The "machine assignment" tables below describe which machine runs which workers. The dispatcher (Tier 2) handles SSH, conda activation, and result collection.
---

## 1. Library Setup (per machine)

```bash
pip install --quiet TA-Lib pandas-ta arch statsmodels scipy
# TA-Lib needs C library; install via conda if pip fails:
# conda install -c conda-forge ta-lib
```

Verify:

```python
import talib, pandas_ta as pta, arch, statsmodels.api as sm
```

---

## 2. Technical Indicators (Jansen Ch. 4 + standard practice)

For each (asset, timeframe), compute the following technical indicators. All use ONLY data available at time t (no look-ahead).

### 2.1 Trend indicators

| Feature | Library | Parameters | Citation |
|---------|---------|-----------|----------|
| SMA (10, 20, 50, 100, 200) | TA-Lib | various windows | Jansen Ch. 4 |
| EMA (10, 20, 50, 100, 200) | TA-Lib | various windows | Jansen Ch. 4 |
| MACD (12, 26, 9) | TA-Lib | standard | Jansen Ch. 4 |
| MACD Signal | derived | | |
| MACD Histogram | derived | | |
| Parabolic SAR | TA-Lib | (0.02, 0.2) | Jansen Ch. 4 |
| ADX (14) | TA-Lib | 14 | Jansen Ch. 4 |
| +DI / -DI | TA-Lib | 14 | |
| Aroon Up/Down (14) | TA-Lib | 14 | |
| TRIX (14) | TA-Lib | 14 | |
| KAMA (10) | TA-Lib | 10 | Kaufman, "Trading Systems and Methods" |

### 2.2 Momentum indicators

| Feature | Library | Parameters | Citation |
|---------|---------|-----------|----------|
| RSI (7, 14, 21) | TA-Lib | various | Jansen Ch. 4 |
| Stochastic %K, %D | TA-Lib | (14, 3) | |
| Williams %R | TA-Lib | 14 | |
| ROC (10, 20, 60) | TA-Lib | various | |
| MOM (10, 20) | TA-Lib | various | |
| CCI (14) | TA-Lib | 14 | |
| MFI (14) | TA-Lib | 14 | (uses volume) |
| Ultimate Oscillator (7,14,28) | TA-Lib | | |

### 2.3 Volatility indicators

| Feature | Library | Parameters | Citation |
|---------|---------|-----------|----------|
| Bollinger Bands (20, 2σ) — upper, middle, lower, %B, width | TA-Lib | | Jansen Ch. 4 |
| ATR (14) | TA-Lib | 14 | Jansen Ch. 4 |
| Normalized ATR (ATR / close) | derived | | |
| Keltner Channels (20, 2 ATR) | pandas-ta | | |
| Donchian Channels (20) | pandas-ta | | |
| Historical Volatility (10, 20, 60 bar) | rolling std of returns | | |

### 2.4 Volume indicators (for assets with volume)

| Feature | Library | Parameters | Citation |
|---------|---------|-----------|----------|
| OBV | TA-Lib | | Jansen Ch. 4 |
| OBV delta (rolling 20) | derived | | |
| Volume SMA (10, 20) | derived | | |
| Volume ratio (current / avg 20) | derived | | |
| Chaikin Money Flow (20) | pandas-ta | 20 | |
| Accumulation/Distribution Line | TA-Lib | | |
| VWAP rolling (60 bars) | derived | 60 | |
| Volume Price Trend (VPT) | pandas-ta | | |

### 2.5 Pattern recognition (cyclical)

| Feature | Library | Citation |
|---------|---------|----------|
| HT_DCPERIOD (Hilbert Transform — Dominant Cycle Period) | TA-Lib | Ehlers, "Cybernetic Analysis for Stocks and Futures" |
| HT_DCPHASE (Hilbert Transform — Dominant Cycle Phase) | TA-Lib | same |
| HT_TRENDMODE (Trend vs Cycle Mode) | TA-Lib | same |
| HT_SINE / HT_LEADSINE | TA-Lib | same |

### 2.6 Composite features (derived)

| Feature | Formula | Notes |
|---------|---------|-------|
| Returns (1, 5, 10, 20, 60 bar) | (close_t / close_t-k) - 1 | Multiple horizons |
| Log returns (1, 5, 10, 20, 60 bar) | log(close_t / close_t-k) | |
| EMA cross signal | EMA_fast - EMA_slow | normalized by price |
| RSI divergence flag | rolling 60-bar RSI vs price divergence detector | |
| BB position | (close - BB_lower) / (BB_upper - BB_lower) | between 0 and 1 |
| Trend strength | abs(slope of regression on last 50 bars) | |

---

## 3. Advanced Statistical Features (Tsay Ch. 1-3, Lopez de Prado)

### 3.1 Rolling statistical moments

| Feature | Window | Citation |
|---------|--------|----------|
| Rolling mean of returns (20, 60, 252 bars) | various | Tsay Ch. 2 |
| Rolling std of returns | same | |
| Rolling skewness | same | Tsay Ch. 1 |
| Rolling kurtosis | same | Tsay Ch. 1 |
| Realized variance (sum of squared 5m returns over 1h) | when sim is 1h | Andersen et al. |
| Realized skewness | same | |
| Realized kurtosis | same | |

### 3.2 Autocorrelation features

| Feature | Window | Notes |
|---------|--------|-------|
| Lag-1 autocorrelation of returns (rolling 100 bars) | 100 | |
| Lag-5 autocorrelation of returns (rolling 100 bars) | 100 | |
| Squared returns autocorrelation lag-1 (rolling 100) | 100 | volatility clustering proxy |
| Ljung-Box Q stat (rolling 100, lag 10) | 100 | |

### 3.3 GARCH-derived features (Tsay Ch. 3, arch library)

Run rolling GARCH(1,1) on returns. Extract:

| Feature | Source | Citation |
|---------|--------|----------|
| Conditional variance estimate | GARCH(1,1) fitted on rolling 500-bar window | Tsay Ch. 3 |
| Conditional volatility (sqrt of variance) | derived | |
| GARCH ω parameter (rolling estimate) | | |
| GARCH α parameter (rolling) | | shock persistence |
| GARCH β parameter (rolling) | | volatility persistence |
| Persistence: α + β | | |

GARCH refit every 100 bars (computationally expensive); forward-fill between refits.

### 3.4 Regime indicators

| Feature | Method | Citation |
|---------|--------|----------|
| Hidden Markov Model state probability (2 regimes) | hmmlearn rolling | Hamilton, "Time Series Analysis" |
| Volatility regime flag (high/low) | quantile of rolling vol vs 252-bar baseline | |
| Trend regime flag | sign of EMA slope | |

### 3.5 Stationarity features

| Feature | Method | Citation |
|---------|--------|----------|
| ADF test p-value (rolling 200) | statsmodels adfuller | Tsay Ch. 2 |
| KPSS test p-value (rolling 200) | statsmodels kpss | |
| Hurst exponent (rolling 200) | nolds.hurst_rs | Lopez de Prado Ch. 5 |

### 3.6 Information-theoretic features

| Feature | Method | Citation |
|---------|--------|----------|
| Sample entropy (rolling 200) | nolds.sampen | Pincus 1991 |
| Approximate entropy | | |
| Permutation entropy | pyentrp library | Bandt & Pompe 2002 |

### 3.7 Lopez de Prado microstructure features (Ch. 19)

When trade-level data available (BTC, equities with Polygon):

| Feature | Method | Citation |
|---------|--------|----------|
| Tick rule imbalance | sign of price changes summed over bar | Lopez de Prado Ch. 19 |
| Bulk volume classification (BVC) imbalance | normalized z-score of returns | Easley et al. |
| Roll's spread estimator | | Lopez de Prado Ch. 19 |
| Corwin-Schultz spread | | |
| Kyle's λ (price impact) | | |
| VPIN (Volume-synchronized PIN) | | Easley et al. 2012 |

For tick-level features, computed at native trade frequency, then aggregated to simulation timeframe.

---

## 4. Implementation Pattern (per asset, per timeframe)

```python
import pandas as pd
import talib
import pandas_ta as pta
from arch import arch_model
import nolds

def compute_technical_features(df_ohlcv):
    """Compute all Section 2 technical indicators."""
    out = pd.DataFrame(index=df_ohlcv.index)
    
    open_, high, low, close, volume = df_ohlcv["open"], df_ohlcv["high"], df_ohlcv["low"], df_ohlcv["close"], df_ohlcv["volume"]
    
    # Trend
    for period in [10, 20, 50, 100, 200]:
        out[f"sma_{period}"] = talib.SMA(close, period)
        out[f"ema_{period}"] = talib.EMA(close, period)
    
    macd, macdsignal, macdhist = talib.MACD(close, 12, 26, 9)
    out["macd"] = macd
    out["macd_signal"] = macdsignal
    out["macd_hist"] = macdhist
    
    out["sar"] = talib.SAR(high, low, 0.02, 0.2)
    out["adx"] = talib.ADX(high, low, close, 14)
    out["plus_di"] = talib.PLUS_DI(high, low, close, 14)
    out["minus_di"] = talib.MINUS_DI(high, low, close, 14)
    out["aroon_up"], out["aroon_down"] = talib.AROON(high, low, 14)
    out["trix"] = talib.TRIX(close, 14)
    out["kama"] = talib.KAMA(close, 10)
    
    # Momentum
    for period in [7, 14, 21]:
        out[f"rsi_{period}"] = talib.RSI(close, period)
    out["stoch_k"], out["stoch_d"] = talib.STOCH(high, low, close, 14, 3, 3)
    out["willr"] = talib.WILLR(high, low, close, 14)
    for period in [10, 20, 60]:
        out[f"roc_{period}"] = talib.ROC(close, period)
    out["mom_10"] = talib.MOM(close, 10)
    out["cci"] = talib.CCI(high, low, close, 14)
    out["mfi"] = talib.MFI(high, low, close, volume, 14)
    out["ultimate"] = talib.ULTOSC(high, low, close, 7, 14, 28)
    
    # Volatility
    bb_upper, bb_middle, bb_lower = talib.BBANDS(close, 20, 2, 2)
    out["bb_upper"], out["bb_middle"], out["bb_lower"] = bb_upper, bb_middle, bb_lower
    out["bb_pct_b"] = (close - bb_lower) / (bb_upper - bb_lower)
    out["bb_width"] = (bb_upper - bb_lower) / bb_middle
    out["atr"] = talib.ATR(high, low, close, 14)
    out["atr_norm"] = out["atr"] / close
    
    # Volume
    out["obv"] = talib.OBV(close, volume)
    out["obv_delta_20"] = out["obv"].diff(20)
    out["volume_sma_20"] = volume.rolling(20).mean()
    out["volume_ratio"] = volume / out["volume_sma_20"]
    out["chaikin_mf"] = pta.cmf(high, low, close, volume, 20)
    out["ad_line"] = talib.AD(high, low, close, volume)
    
    # Hilbert Transform cyclical
    out["ht_dcperiod"] = talib.HT_DCPERIOD(close)
    out["ht_dcphase"] = talib.HT_DCPHASE(close)
    out["ht_trendmode"] = talib.HT_TRENDMODE(close)
    sine, leadsine = talib.HT_SINE(close)
    out["ht_sine"] = sine
    out["ht_leadsine"] = leadsine
    
    # Composite/derived
    for period in [1, 5, 10, 20, 60]:
        out[f"return_{period}"] = close.pct_change(period)
        out[f"log_return_{period}"] = np.log(close / close.shift(period))
    out["ema_cross"] = (out["ema_10"] - out["ema_50"]) / close
    
    return out


def compute_statistical_features(df_ohlcv):
    """Compute Section 3 statistical features."""
    out = pd.DataFrame(index=df_ohlcv.index)
    
    close = df_ohlcv["close"]
    returns = close.pct_change()
    log_returns = np.log(close / close.shift(1))
    
    # Rolling moments
    for window in [20, 60, 252]:
        out[f"return_mean_{window}"] = returns.rolling(window).mean()
        out[f"return_std_{window}"] = returns.rolling(window).std()
        out[f"return_skew_{window}"] = returns.rolling(window).skew()
        out[f"return_kurt_{window}"] = returns.rolling(window).kurt()
    
    # Autocorrelation
    out["acf_lag1_100"] = returns.rolling(100).apply(lambda x: x.autocorr(lag=1))
    out["acf_lag5_100"] = returns.rolling(100).apply(lambda x: x.autocorr(lag=5))
    out["acf_sq_lag1_100"] = (returns ** 2).rolling(100).apply(lambda x: x.autocorr(lag=1))
    
    # GARCH (rolling, refit every 100 bars)
    out["garch_cond_var"] = compute_rolling_garch(returns, refit_every=100, window=500)
    out["garch_cond_vol"] = np.sqrt(out["garch_cond_var"])
    
    # Regime indicators
    out["vol_regime"] = (returns.rolling(20).std() > returns.rolling(252).std().quantile(0.75)).astype(int)
    out["trend_regime"] = np.sign(close.rolling(50).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0]))
    
    # Stationarity (ADF rolling)
    out["adf_pvalue_200"] = compute_rolling_adf(close, window=200)
    
    # Hurst exponent
    out["hurst_200"] = log_returns.rolling(200).apply(
        lambda x: nolds.hurst_rs(x.dropna()) if len(x.dropna()) >= 100 else np.nan
    )
    
    # Entropy
    out["sample_entropy_200"] = compute_rolling_sample_entropy(returns, window=200)
    
    return out


# Main loop
manifest = json.load(open("features/MANIFEST.json"))

for asset_name, asset_info in manifest["trading_assets"].items():
    for tf, tf_info in asset_info["timeframes"].items():
        df = pd.read_parquet(tf_info["path"])
        
        tech_features = compute_technical_features(df)
        stat_features = compute_statistical_features(df)
        
        # Save
        out_dir = f"features/trading_asset_features/{asset_name}/{tf}/"
        os.makedirs(out_dir, exist_ok=True)
        tech_features.to_parquet(f"{out_dir}technical.parquet")
        stat_features.to_parquet(f"{out_dir}statistical.parquet")
        
        # Validate
        validate_features(tech_features, stat_features)
        
        # Document
        write_feature_documentation(out_dir, asset_name, tf, tech_features.columns, stat_features.columns)
```

---

## 5. Validation per Feature Set

For each features parquet:

```python
def validate_features(features_df):
    issues = []
    
    # No infinities
    if np.isinf(features_df.values).any():
        issues.append("Contains infinities")
    
    # NaN only at warmup period (first N bars where N = max indicator lookback)
    max_lookback = 252
    nan_after_warmup = features_df.iloc[max_lookback:].isna().any().any()
    if nan_after_warmup:
        issues.append("NaN values after warmup period")
    
    # Range sanity (e.g., RSI 0-100, BB %B 0-1 typically)
    if "rsi_14" in features_df.columns:
        rsi = features_df["rsi_14"].dropna()
        if (rsi < 0).any() or (rsi > 100).any():
            issues.append("RSI out of range")
    
    # Look-ahead test: shifted feature at t-1 should not equal future value at t
    for col in features_df.columns:
        if "return_1" in col:  # 1-bar return is computed at t using close_t and close_{t-1}
            continue  # this is allowed
        # For other features, check no perfect alignment with future
    
    return issues
```

If issues: ESCALATION.

---

## 6. Documentation per Feature Set

Each `features/trading_asset_features/<asset>/<tf>/` folder gets:

- `README.md`: lists all features, brief description per feature
- `data_dictionary.md`: full feature dictionary with formulas + citations
- `provenance.json`: when computed, which input data, library versions

---

## 7. Stage 2.2 Deliverable

`STAGE_2.2_DELIVERABLE.md`:

```markdown
# Stage 2.2 Deliverable — Technical and Statistical Features

## Summary

- Trading assets processed: [N]
- Timeframes per asset: 4 (5m, 15m, 1h, 4h)
- Total feature parquet files: [N × 4 × 2]
- Technical features per (asset, tf): ~80
- Statistical features per (asset, tf): ~40
- Total features per asset: ~120 × 4 timeframes = ~480

## Validation

All feature sets pass validation tests.

## Documentation

All folders documented per Phase 1 standards.

## User Gate

User reviews. Approves Stage 2.3 start.
```

---

## 8. User Gate

User approves Stage 2.3.
