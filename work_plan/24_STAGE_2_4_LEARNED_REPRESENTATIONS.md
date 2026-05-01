# Stage 2.4 — Learned Representations

**Stage goal:** Produce learned feature representations using autoencoders and embeddings via the existing `feature-extractor` repo. Includes CVAE, transformer, LSTM, CNN, VAE variants. Document tokenization options for transformer-based RL policies.

**Inputs:** Stages 2.1, 2.2, 2.3 complete. Has technical, statistical, signal decomposition features available.

**Outputs:**
- `features/trading_asset_features/<asset>/<tf>/learned_<method>.parquet` per autoencoder variant
- Trained autoencoder model checkpoints
- Per-method documentation
- `STAGE_2.4_DELIVERABLE.md`

**Machine assignment:**
- **Dragon (RTX 4090):** PRIMARY — autoencoder training (heaviest GPU work)
- **Gamma (RTX 5070 Ti):** Secondary autoencoder training (parallel for different methods)
- **Omega:** Inference + feature extraction (lighter, plus CPU coordination)

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

## 1. Reuse Existing Infrastructure

The existing `feature-extractor` repo contains autoencoder plugins. Per Project 3 master plan Rule M.6 + Phase 2 Rule P2.6, we REUSE these — do NOT reimplement.

```bash
cd /home/harveybc/Documents/GitHub/feature-extractor
git pull
python -c "from feature_extractor import load_config; print('OK')"
```

The `feature-extractor` plugin architecture provides at minimum:
- Transformer autoencoder (encoder/decoder both transformer-based)
- LSTM autoencoder
- CNN autoencoder (1D conv on time series)
- VAE (Variational Autoencoder)
- CVAE (Conditional VAE) — used in Project 2 Part III planning

Verify which plugins are actually present:

```bash
ls /home/harveybc/Documents/GitHub/feature-extractor/feature_extractor/plugins/
```

---

## 1.5 GPU Lockfile (mandatory for this stage)

This is the heaviest GPU stage of Phase 2. Autoencoder training runs for hours and competes directly with the local Hermes/Gemma supervisors on Dragon and Gamma. Per master plan Rule M.14 and `01_AGENT_INFRASTRUCTURE.md` §4:

Every training script MUST acquire `/tmp/gpu_busy.lock` before instantiating a model on GPU, and release it on exit.

Training script template (use this pattern for all variants):

```python
import sys
sys.path.insert(0, "/home/harveybc/Documents/GitHub/financial-data/_scripts/lib")
from gpu_lock import acquire_gpu_lock, release_gpu_lock

acquire_gpu_lock(
    command=" ".join(sys.argv),
    expected_duration_minutes=180,  # 3h estimate per AE training; tune per variant
    stage="2.4",
)
try:
    # ... import torch/tf, build model, train ...
    pass
finally:
    release_gpu_lock()
```

For this stage, set the cron interval on Dragon and Gamma to **15 min** (per infrastructure doc §4.5). Tier 1 supervisor ticks during this stage will frequently log `skipped_gpu_busy` — that is expected and not a problem.

---

## 2. Encoding Strategy per Asset/Timeframe

Each autoencoder is trained on the trading asset's price + technical features at a specific timeframe to produce a low-dimensional embedding.

### Encoding inputs

For each (asset, timeframe), the autoencoder input is a window of multi-channel data:

```
input shape: (batch, window_length, n_features)

window_length: 64 (configurable per timeframe, e.g. larger for 4h)
n_features: ~80 (selected from technical + statistical features at the timeframe)
```

Selected input features (Phase 2.2 + 2.3 outputs combined into normalized matrix):
- OHLCV (5 features)
- Selected technical (RSI, MACD hist, BB %B, ATR norm, EMA cross, OBV delta, MFI, CCI, etc.)  ~25 features
- Selected statistical (rolling std, skew, kurt, GARCH cond_vol, hurst)  ~15 features
- Selected wavelet (5 levels of energy + entropy)  ~10 features
- Selected Hilbert (amplitude, inst freq)  ~3 features
- Selected EMD (IMF1-3)  ~3 features
- Selected fracdiff (optimal d)  ~1 feature

Total ~60-80 input features per bar.

### Encoder output (embedding)

Latent dimension typically 16-32 (configurable per autoencoder type).

The embedding at time t represents a compressed summary of the past `window_length` bars.

---

## 3. Autoencoder Variants

### 3.1 Transformer Autoencoder

**Architecture (from feature-extractor repo):**

- Encoder: 2-4 transformer layers, multi-head attention, positional encoding
- Decoder: symmetric transformer layers
- Latent: pooled output of encoder

**Hyperparameters to GA-tune later (in Phase 3 if needed):**
- `n_heads`: 4, 8, 16
- `n_layers`: 2, 4, 6
- `d_model`: 64, 128, 256
- `latent_dim`: 16, 32, 64
- `window_length`: 32, 64, 128

**Training:**

```bash
# On Dragon
ssh dragon "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && \
  cd /home/harveybc/Documents/GitHub/feature-extractor && \
  python -m feature_extractor train \
    --plugin transformer \
    --config examples/config/transformer_p3_btcusdt_1h.json \
    --train_data /home/harveybc/Documents/GitHub/financial-data/features/.../d4_norm.csv \
    --val_data /home/harveybc/Documents/GitHub/financial-data/features/.../d5_norm.csv \
    --output_dir /home/harveybc/Documents/GitHub/financial-data/features/learned_models/btcusdt/1h/transformer/"
```

**Output:**
- Trained model: `learned_models/<asset>/<tf>/transformer/model.h5`
- Encoded features for full data range: `features/trading_asset_features/<asset>/<tf>/learned_transformer.parquet`

### 3.2 LSTM Autoencoder

Same pattern, plugin = `lstm`.

Architecture: Stacked LSTM encoder → bottleneck → stacked LSTM decoder.

Hyperparameters:
- `lstm_units`: 64, 128
- `n_layers`: 2, 3
- `latent_dim`: 16, 32
- `window_length`: 32, 64

### 3.3 CNN Autoencoder

Plugin = `cnn`.

Architecture: 1D conv layers (encoder) + 1D transposed conv layers (decoder). Treats multi-feature time series as 2D input.

Hyperparameters:
- `n_filters`: 32, 64, 128
- `kernel_size`: 3, 5, 7
- `n_conv_layers`: 3, 4
- `latent_dim`: 16, 32

### 3.4 VAE (Variational Autoencoder)

Plugin = `vae`.

Standard VAE with KL divergence regularization. Provides probabilistic embedding (mean + log-variance) instead of deterministic.

Output: latent mean and log-variance per timestamp. Use mean as feature, log-variance as uncertainty proxy.

### 3.5 CVAE (Conditional VAE) — used in Project 2 Stage III planning

Plugin = `cvae`.

VAE conditioned on auxiliary signal (e.g., regime label, day-of-week). Useful when conditioning information available.

For Project 3, condition on volatility regime (high/low computed at training time).

---

## 4. Training Procedure

### 4.1 Train/Val/Test split

Per Rule M.3:
- Training: 2017-2023 (crypto) or 2005-2023 (FX) — whatever asset history allows
- Validation: 2024 (in-sample tail, used for hyperparameter selection)
- Held-out: 2025 (NEVER used during AE training)

### 4.2 Normalization

Use StandardScaler fit on TRAINING split only:

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
scaler.fit(X_train)  # train data only

X_train_norm = scaler.transform(X_train)
X_val_norm = scaler.transform(X_val)
X_test_norm = scaler.transform(X_test)

# Save scaler for inference + Phase 3
joblib.dump(scaler, "learned_models/<asset>/<tf>/<method>/scaler.pkl")
```

### 4.3 Loss + early stopping

Reconstruction loss: MSE for deterministic AEs, ELBO (recon + KL) for VAEs.

Early stopping based on validation reconstruction loss with patience = 20 epochs.

Save best model (lowest val loss) checkpoint.

### 4.4 Inference (encode full data range)

After training, run encoder over ENTIRE data range (train + val + test) to produce embeddings:

```python
# Causal sliding window
embeddings = []
for end_idx in range(window_length, len(data)):
    window = data.iloc[end_idx - window_length:end_idx].values
    z = encoder.predict(window[None, ...])[0]  # batch dim
    embeddings.append(z)

# Save as parquet aligned with timestamps
```

CRITICAL: Even though encoder was trained on train-only, the inference produces embeddings for ALL timestamps (train + val + test). The Phase 3 RL agents see only train+val embeddings during training; held-out (2025) embeddings used only at final evaluation.

---

## 5. Tokenization Options for Transformer-based RL Policies

For experimental Phase 3 configurations using transformer policies, observation space can be tokenized.

### 5.1 Discrete tokenization (KMeans)

Cluster the autoencoder embeddings into discrete codes:

```python
from sklearn.cluster import MiniBatchKMeans

n_codes = 256  # or 512, 1024
kmeans = MiniBatchKMeans(n_clusters=n_codes, batch_size=10000)
kmeans.fit(train_embeddings)

# Assign code per timestamp
codes = kmeans.predict(all_embeddings)  # shape (T,)

# Save
np.save(f"learned_models/<asset>/<tf>/<method>/kmeans_codes_{n_codes}.npy", codes)
```

This produces an integer sequence of codes per asset/timeframe. Suitable for transformer policies that consume tokens.

### 5.2 VQ-VAE tokenization

If VQ-VAE plugin available in feature-extractor, use vector quantization for end-to-end discrete codes.

### 5.3 Continuous embeddings (default)

Most RL policies (PPO, SAC, DQN with MlpPolicy) consume continuous features directly. Use the autoencoder mean output as a continuous feature vector.

---

## 6. Phase 3 Compatibility

Each autoencoder produces parquet files at `features/trading_asset_features/<asset>/<tf>/learned_<method>.parquet`.

Schema:
- index: timestamp
- columns: `latent_0, latent_1, ..., latent_<latent_dim - 1>`
- For VAE/CVAE: also `latent_logvar_0, ...` (uncertainty)

These columns become candidate features for Phase 3 experiments. The experiment framework (Stage 3.1) decides which (asset, timeframe, feature combination) to test.

---

## 7. Per-Method State of the Art Notes

### Why include ALL of (transformer, LSTM, CNN, VAE, CVAE)?

Per master plan §10 (Risk acknowledgment): we don't know in advance which architecture will produce best embeddings for RL trading. Phase 3 systematically evaluates each variant.

State of the art per architecture:

| Architecture | Strengths | Weaknesses | Best for |
|--------------|-----------|------------|----------|
| Transformer | Captures long-range dependencies, parallelizable | Computationally expensive, needs more data | High-data settings (BTC 5m has millions of bars) |
| LSTM | Classic for time series, smaller compute | Sequential bottleneck, can struggle with very long contexts | Medium-data settings, FX hourly |
| CNN | Fast inference, captures local patterns | Limited receptive field | Real-time signal extraction |
| VAE | Probabilistic embeddings = uncertainty proxy | Reconstruction can be blurry | When uncertainty matters |
| CVAE | Conditioning improves separation | Need good conditioning signal | When regime labels available |

### State-of-the-art alternatives NOT in feature-extractor

If feature-extractor lacks these, do NOT add new plugins (Rule P2.6 reuse only). Document as future work:
- Time2Vec embeddings (Kazemi et al. 2019)
- Informer (Zhou et al. 2021) — efficient transformer for long sequences
- TFT (Lim et al. 2021) — Temporal Fusion Transformer
- PatchTST (Nie et al. 2023)
- TimesNet (Wu et al. 2023)
- N-BEATS, N-HiTS

These are state-of-the-art research-grade. If user wants in Project 4, they're cataloged.

---

## 8. Implementation Checklist

For each (asset, timeframe, autoencoder_variant):

1. Load input data (technical + statistical + decomposition features from previous stages)
2. Train/val/test split (2024 boundary)
3. Fit StandardScaler on train, transform all splits
4. Train autoencoder via feature-extractor repo
5. Save model checkpoint + scaler
6. Run inference on full data range with causal sliding window
7. Save embeddings parquet
8. Validate (no NaNs after warmup, no infinities, embeddings dimension matches config)
9. Write `<method>_README.md` with citation, hyperparameters, training metrics
10. Write provenance.json

---

## 9. Stage 2.4 Deliverable

`STAGE_2.4_DELIVERABLE.md`:

```markdown
# Stage 2.4 Deliverable — Learned Representations

## Autoencoder Variants Trained

| Variant | Plugin | Trained per (asset, tf) |
|---------|--------|--------------------------|
| Transformer | transformer | YES |
| LSTM | lstm | YES |
| CNN | cnn | YES |
| VAE | vae | YES |
| CVAE | cvae | YES (where regime conditioning available) |

## Coverage

- Trading assets: [N]
- Timeframes: 4 per asset
- Variants per (asset, tf): up to 5
- Total models trained: up to N × 4 × 5

## Training Metrics Summary

| Variant | Average reconstruction val loss | Average training time per (asset, tf) |
|---------|-----|-----|
| Transformer | X | Y hours |
| ... | | |

## Embeddings Produced

For each (asset, tf, variant): `features/trading_asset_features/<asset>/<tf>/learned_<variant>.parquet`

Total embedding parquet files: [N × 4 × 5]

## Tokenization

For each variant, optional discrete code sequences produced via KMeans:
- 256 codes
- 512 codes
- 1024 codes

Available at `learned_models/<asset>/<tf>/<method>/kmeans_codes_<N>.npy`

## Validation

All embeddings pass validation (no NaN after warmup, no infinity, dimensions match config).

## Phase 3 Readiness

All Phase 2 outputs ready for Phase 3 systematic experiments.

## User Gate

User reviews Phase 2 outputs. Approves Phase 3 start.
```

---

## 10. User Gate

User reviews complete Phase 2 output. Approves Phase 3 start.
