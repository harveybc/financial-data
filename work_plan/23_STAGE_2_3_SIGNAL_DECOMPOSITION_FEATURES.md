# Stage 2.3 — Signal Decomposition Features

**Stage goal:** Compute signal decomposition features that extract multi-resolution structure from price time series. Includes wavelet, Hilbert transform, multitaper spectral, EMD/EEMD, and Lopez de Prado's fractional differentiation.

**Inputs:** Stage 2.1 complete (multi-timeframe data). Stage 2.2 may run in parallel.

**Outputs:**
- `features/trading_asset_features/<asset>/<tf>/wavelet.parquet`
- `features/trading_asset_features/<asset>/<tf>/hilbert.parquet`
- `features/trading_asset_features/<asset>/<tf>/multitaper.parquet`
- `features/trading_asset_features/<asset>/<tf>/emd.parquet`
- `features/trading_asset_features/<asset>/<tf>/fracdiff.parquet`
- Per-feature documentation with citations
- `STAGE_2.3_DELIVERABLE.md`

**Machine assignment:**
- **Omega:** FX assets (lighter compute)
- **Dragon:** Crypto top 50 (Wavelets + EMD heaviest)
- **Gamma:** Multitaper spectral (computationally intensive on heavier crypto data)

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

## 1. Library Setup

```bash
pip install --quiet PyWavelets scipy nitime PyEMD pyhht
# nitime for multitaper; PyEMD for EMD; pyhht for Hilbert-Huang Transform
```

Verify:

```python
import pywt, scipy.signal, nitime.algorithms as nialg, PyEMD
```

---

## 2. Wavelet Features (Tsay Ch. 1, Mallat "A Wavelet Tour of Signal Processing")

### 2.1 Discrete Wavelet Transform (DWT)

For each (asset, timeframe), compute multi-level DWT decomposition:

```python
import pywt

def compute_dwt_features(close_series, wavelet="db4", levels=4):
    """Compute multi-level DWT features.
    
    Returns coefficients at each level + reconstructed components.
    Uses 'sym' boundary mode (no future leak).
    """
    out = pd.DataFrame(index=close_series.index)
    
    # Run DWT in rolling window to maintain causality
    window = 256  # power of 2 for clean DWT
    
    for end_idx in range(window, len(close_series)):
        segment = close_series.iloc[end_idx - window:end_idx].values
        
        # DWT decomposition
        coeffs = pywt.wavedec(segment, wavelet, level=levels)
        # coeffs[0] = approximation coefficients (low frequency)
        # coeffs[1..levels] = detail coefficients (high to low)
        
        # Extract features at the END of the window (no future leak)
        for level, c in enumerate(coeffs):
            out.iloc[end_idx, ...] = features_from_coeffs(c, level)
    
    return out
```

**Causality consideration:** Standard DWT is non-causal (uses future bars in symmetric padding). To make causal:
- Use only past data in each rolling window
- Take the LAST element of each detail series
- This is approximate; for true causal use Maximal Overlap DWT (MODWT) with one-sided padding

```python
import pywt

def compute_modwt_features(close_series, wavelet="la8", levels=4):
    """Maximal Overlap DWT — preserves time alignment."""
    # Use shift-invariant variant
    coeffs_modwt = pywt.swt(close_series.values, wavelet, level=levels)
    # ... extract coefficients aligned with each timestamp
```

### 2.2 Wavelet feature columns produced

| Feature | Description | Citation |
|---------|-------------|----------|
| `wavelet_approx_L4` | Approximation at level 4 (lowest frequency / trend) | Mallat |
| `wavelet_detail_L1` | Detail at level 1 (highest frequency / noise) | |
| `wavelet_detail_L2` | Detail at level 2 | |
| `wavelet_detail_L3` | Detail at level 3 | |
| `wavelet_detail_L4` | Detail at level 4 (mid-frequency cycles) | |
| `wavelet_energy_L1..L4` | Energy at each level (sum of squared coefficients) | |
| `wavelet_entropy` | Wavelet entropy across levels | Rosso et al. 2006 |
| `wavelet_relative_energy_Lk` | Energy at level k / total energy | |

Use Daubechies-4 (`db4`) wavelet as default. Other wavelets (Symlet, Coiflet) optionally tested.

### 2.3 Continuous Wavelet Transform (CWT) — selected scales

For more refined multi-resolution features, also compute CWT at specific scales using Morlet wavelet:

```python
from scipy.signal import cwt, morlet2

def compute_cwt_features(close_series, scales=[4, 8, 16, 32, 64, 128]):
    out = pd.DataFrame(index=close_series.index)
    
    for end_idx in range(max(scales) * 2, len(close_series)):
        segment = close_series.iloc[end_idx - max(scales) * 2:end_idx].values
        coefs = cwt(segment, morlet2, scales)
        # Last column of coefs corresponds to current time
        for s_idx, s in enumerate(scales):
            out.iloc[end_idx, ...] = abs(coefs[s_idx, -1])  # magnitude at current time
    
    return out
```

CWT magnitude at multiple scales = power at multiple "cycles per N bars."

---

## 3. Hilbert Transform Features (Ehlers, "Cybernetic Analysis for Stocks and Futures")

Note: TA-Lib provides basic HT functions used in Stage 2.2. Stage 2.3 adds advanced HT-derived features:

```python
from scipy.signal import hilbert

def compute_hilbert_features(close_series):
    """Hilbert Transform — instantaneous amplitude + phase + frequency."""
    out = pd.DataFrame(index=close_series.index)
    
    # Detrended close (remove low-freq drift)
    detrended = close_series - close_series.rolling(50).mean()
    
    # Apply Hilbert transform (causal version: rolling window)
    window = 100
    
    for end_idx in range(window, len(close_series)):
        segment = detrended.iloc[end_idx - window:end_idx].values
        analytic = hilbert(segment)
        
        amplitude = np.abs(analytic)
        phase = np.angle(analytic)
        
        # Instantaneous frequency = derivative of phase
        inst_freq = np.diff(np.unwrap(phase))
        
        out.loc[close_series.index[end_idx], "ht_amplitude"] = amplitude[-1]
        out.loc[close_series.index[end_idx], "ht_phase"] = phase[-1]
        out.loc[close_series.index[end_idx], "ht_inst_freq"] = inst_freq[-1] if len(inst_freq) > 0 else np.nan
    
    return out
```

Features produced:

| Feature | Description | Citation |
|---------|-------------|----------|
| `ht_amplitude` | Instantaneous amplitude (envelope) | Ehlers Ch. 9 |
| `ht_phase` | Instantaneous phase (radians) | |
| `ht_inst_freq` | Instantaneous frequency (cycles per bar) | |
| `ht_amplitude_zscore_100` | Amplitude z-scored over 100 bars | |
| `ht_phase_difference` | Difference in phase between current and 1 bar ago | |

---

## 4. Multitaper Spectral Features (Tsay Ch. 12, Percival & Walden "Spectral Analysis for Physical Applications")

Multitaper is the gold-standard method for spectral density estimation, providing better variance reduction than periodogram or Welch's method.

```python
import nitime.algorithms as nialg

def compute_multitaper_features(returns_series, NW=4, K=7, freqs_of_interest=None):
    """
    Multitaper spectral estimate using DPSS tapers.
    NW = time-bandwidth product
    K = number of tapers (typically 2*NW - 1)
    """
    out = pd.DataFrame(index=returns_series.index)
    
    window = 256  # rolling window
    
    if freqs_of_interest is None:
        freqs_of_interest = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4]  # cycles per bar
    
    for end_idx in range(window, len(returns_series)):
        segment = returns_series.iloc[end_idx - window:end_idx].values
        if np.isnan(segment).any():
            continue
        
        f, psd_mt, _ = nialg.multi_taper_psd(segment, Fs=1.0, NW=NW, BW=None, adaptive=True, jackknife=False)
        
        # Extract power at frequencies of interest
        for f_target in freqs_of_interest:
            f_idx = np.argmin(np.abs(f - f_target))
            out.loc[returns_series.index[end_idx], f"mt_psd_{f_target}"] = psd_mt[f_idx]
        
        # Total spectral entropy
        psd_norm = psd_mt / psd_mt.sum()
        spec_entropy = -np.sum(psd_norm * np.log(psd_norm + 1e-12))
        out.loc[returns_series.index[end_idx], "mt_spec_entropy"] = spec_entropy
    
    return out
```

Features produced:

| Feature | Description | Citation |
|---------|-------------|----------|
| `mt_psd_0.05` | Power at 0.05 cycles/bar (slow cycle) | Percival & Walden |
| `mt_psd_0.1`, `mt_psd_0.15`, ... | Power at various frequencies | |
| `mt_spec_entropy` | Spectral entropy | Inouye et al. 1991 |
| `mt_dominant_freq` | Frequency with maximum power | |
| `mt_spectral_centroid` | Weighted average frequency | |

Computational expense: multitaper is O(N²) per window. For 5m data over multiple years, computational time substantial.

---

## 5. Empirical Mode Decomposition (EMD/EEMD) (Huang et al. 1998)

EMD decomposes a non-stationary time series into Intrinsic Mode Functions (IMFs) — adaptively chosen frequency components.

```python
from PyEMD import EMD, EEMD

def compute_emd_features(close_series, max_imfs=5):
    """EMD decomposition — extract first N IMFs."""
    out = pd.DataFrame(index=close_series.index)
    
    window = 512
    
    for end_idx in range(window, len(close_series)):
        segment = close_series.iloc[end_idx - window:end_idx].values
        
        emd = EMD()
        imfs = emd(segment)
        
        # Extract last value of each IMF
        for i in range(min(max_imfs, len(imfs))):
            out.loc[close_series.index[end_idx], f"emd_imf{i+1}"] = imfs[i][-1]
        
        # Residue (trend)
        if len(imfs) > 0:
            residue = segment - imfs.sum(axis=0)
            out.loc[close_series.index[end_idx], "emd_residue"] = residue[-1]
    
    return out
```

Features produced:

| Feature | Description | Citation |
|---------|-------------|----------|
| `emd_imf1` | First IMF (highest frequency oscillation) | Huang 1998 |
| `emd_imf2` to `emd_imf5` | Successive IMFs (lower frequencies) | |
| `emd_residue` | Trend after removing IMFs | |
| `emd_imf1_energy` | Sum of squared IMF1 over recent window | |

EEMD (Ensemble EMD) is more robust to mode mixing but ~100× slower. Use EMD by default; EEMD optional for selected assets.

---

## 6. Fractional Differentiation (Lopez de Prado Ch. 5)

Fractional differentiation makes a time series stationary while preserving as much memory as possible. Critical for ML on price series.

```python
def fractional_difference(series, d, threshold=1e-4):
    """
    Lopez de Prado fixed-window fractional differentiation.
    d: differentiation order (0 < d < 1)
    threshold: weight cutoff
    """
    # Compute weights
    weights = [1.0]
    k = 1
    while True:
        w_k = -weights[-1] * (d - k + 1) / k
        if abs(w_k) < threshold:
            break
        weights.append(w_k)
        k += 1
    
    weights = np.array(weights[::-1])
    width = len(weights)
    
    # Apply (causal — uses only past values)
    out = np.full(len(series), np.nan)
    for i in range(width - 1, len(series)):
        out[i] = np.dot(weights, series.iloc[i - width + 1:i + 1].values)
    
    return pd.Series(out, index=series.index)


def compute_fracdiff_features(close_series):
    """Compute fractionally differentiated price at multiple d values."""
    out = pd.DataFrame(index=close_series.index)
    
    log_price = np.log(close_series)
    
    for d in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        out[f"fracdiff_d{d}"] = fractional_difference(log_price, d)
    
    # Find optimal d (minimum d that achieves stationarity per ADF test)
    # This is per-asset, computed once and reported
    
    return out
```

Features produced:

| Feature | Description | Citation |
|---------|-------------|----------|
| `fracdiff_d0.1` to `fracdiff_d0.8` | Fractionally differentiated log price at d = 0.1...0.8 | Lopez de Prado Ch. 5 |
| `fracdiff_optimal` | Series at d* (minimum d for stationarity per asset) | |

The optimal d is asset-specific (typically 0.3-0.5 for crypto, 0.4-0.6 for FX). Determined empirically via grid search at acquisition.

---

## 7. Implementation per Asset/Timeframe

**GPU lockfile note:** Multitaper spectral on long crypto 5m series can pin a GPU for many minutes if accelerated (and CPU-bound runs for hours). Per master plan Rule M.14, the orchestrating script wraps the long-running computations with `acquire_gpu_lock` / `release_gpu_lock`:

```python
import sys
sys.path.insert(0, "/home/harveybc/Documents/GitHub/financial-data/_scripts/lib")
from gpu_lock import acquire_gpu_lock, release_gpu_lock

# Wrap heavy computations
acquire_gpu_lock(
    command=f"signal_decomposition {asset_name} {tf}",
    expected_duration_minutes=60,
    stage="2.3",
)
try:
    # ... main loop below ...
    pass
finally:
    release_gpu_lock()
```

For Stage 2.3, set Tier 1 cron interval to **15 min** on the assigned machine (per `01_AGENT_INFRASTRUCTURE.md` §4.5).

```python
# Main loop
manifest = json.load(open("features/MANIFEST.json"))

DECOMPOSITION_METHODS = {
    "wavelet": compute_dwt_features,
    "hilbert": compute_hilbert_features,
    "multitaper": compute_multitaper_features,
    "emd": compute_emd_features,
    "fracdiff": compute_fracdiff_features,
}

for asset_name, asset_info in manifest["trading_assets"].items():
    for tf, tf_info in asset_info["timeframes"].items():
        df = pd.read_parquet(tf_info["path"])
        close = df["close"]
        returns = close.pct_change()
        
        out_dir = f"features/trading_asset_features/{asset_name}/{tf}/"
        os.makedirs(out_dir, exist_ok=True)
        
        for method_name, method_func in DECOMPOSITION_METHODS.items():
            input_series = returns if method_name == "multitaper" else close
            features = method_func(input_series)
            
            # Validate
            validate_features(features)
            
            # Save
            features.to_parquet(f"{out_dir}{method_name}.parquet")
            
            # Document
            write_method_documentation(out_dir, method_name)
```

---

## 8. Validation

Each decomposition method's output validated:

- No infinities
- NaN only at warmup period (depends on method window)
- For wavelets: reconstruction (sum of details + approximation) approximates original within tolerance
- For EMD: IMFs orthogonality property approximately holds
- For fracdiff: ADF test confirms stationarity at chosen d
- Look-ahead test: feature_t computed only with data ≤ t (verified by passing future data and confirming feature unchanged)

---

## 9. Documentation per Method

Per technique, a comprehensive `<method>_README.md` in the asset's timeframe folder:

```markdown
# Wavelet Features — EUR/USD 1h

## Method

Discrete Wavelet Transform (DWT) using Daubechies-4 wavelet, 4 decomposition levels.

## Citation

Mallat (1999), "A Wavelet Tour of Signal Processing"

## Features Produced

[list with descriptions]

## Computational Notes

- Rolling window: 256 bars (power of 2 for clean DWT)
- Causal: each feature at time t uses only data ≤ t
- Library: PyWavelets v1.X.X

## Validation Status

[results]
```

---

## 10. Stage 2.3 Deliverable

`STAGE_2.3_DELIVERABLE.md`:

```markdown
# Stage 2.3 Deliverable — Signal Decomposition Features

## Decomposition Methods Implemented

| Method | Library | Citation |
|--------|---------|----------|
| Discrete Wavelet Transform | PyWavelets | Mallat 1999 |
| Continuous Wavelet Transform | scipy.signal | |
| Hilbert Transform | scipy.signal | Ehlers Cybernetic Analysis |
| Multitaper Spectral | nitime | Percival & Walden |
| EMD / EEMD | PyEMD | Huang 1998 |
| Fractional Differentiation | custom | Lopez de Prado 2018 Ch. 5 |

## Coverage

- Trading assets processed: [N]
- Timeframes per asset: 4
- Total feature parquet files: [N × 4 × 5 methods] = [count]

## Computational Notes

- Total compute time: [X] hours
- Heaviest method: multitaper on 5m crypto data (~XX hours per asset)
- Lightest method: fracdiff (~Y minutes per asset)

## Validation

All feature sets pass validation. Look-ahead tests pass.

## User Gate

User reviews. Approves Stage 2.4 start.
```

---

## 11. User Gate

User approves Stage 2.4.
