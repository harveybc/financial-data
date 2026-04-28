# Phase 2 Overview — Feature Engineering

**Phase goal:** Convert raw data acquired in Phase 1 into a comprehensive feature library across multiple periodicities and engineering techniques. Produce features ready for use as RL agent observation inputs.

**Phase output:** Feature library at `~/Documents/financial_data/features/` with:
- Trading asset price features at 5m, 15m, 1h, 4h
- Forward-filled feature inputs aligned to each simulation timeframe
- Multiple feature engineering technique outputs (technical, statistical, signal decomposition, learned representations)
- Each feature set documented and validated

---

## 1. Critical Distinction Reminder (from master plan §2)

Phase 2 produces features for two different uses:

**Trading asset features:**
- Computed from the asset's own price/volume data
- At simulation timeframes (5m, 15m, 1h, 4h)
- Used in observation space when that asset is being traded

**Cross-source feature inputs:**
- Computed from many other data sources (FRED macro, equity indices, on-chain, etc.)
- At native frequency, then forward-filled or aggregated to simulation timeframe
- Used in observation space alongside trading asset features

Both go into Phase 3 RL agent observation space.

---

## 2. Phase 2 Stages

| Stage | Document | Purpose |
|-------|----------|---------|
| 2.1 | `21_STAGE_2.1_DOWNSAMPLING_AND_RESAMPLING.md` | Multi-timeframe alignment of all data |
| 2.2 | `22_STAGE_2.2_TECHNICAL_AND_STATISTICAL_FEATURES.md` | Standard + advanced statistical features |
| 2.3 | `23_STAGE_2.3_SIGNAL_DECOMPOSITION_FEATURES.md` | Wavelet, Hilbert, multitaper, EMD, fractional differentiation |
| 2.4 | `24_STAGE_2.4_LEARNED_REPRESENTATIONS.md` | Autoencoders + embeddings (CVAE, transformer, LSTM via feature-extractor repo) |

---

## 3. Stage Dependencies

```
2.1 Downsampling/Resampling (foundation — produces aligned multi-TF data)
    │
    ├──▶ 2.2 Technical + Statistical Features (parallel start)
    │
    ├──▶ 2.3 Signal Decomposition Features (parallel start)
    │
    └──▶ 2.4 Learned Representations (depends on outputs of 2.2 + 2.3)
```

Stages 2.2 and 2.3 can run in parallel after 2.1 complete. 2.4 needs both as inputs.

---

## 4. Phase 2 Standing Rules

### Rule P2.1: Features serve RL agents, not predictions

Per master plan Rule M.12: features are observation space inputs for RL policy learning, NOT predictive signals. The criterion for including a feature is: "does it provide useful state information for an RL agent?" — NOT "does it predict future returns?"

### Rule P2.2: All features computed at simulation timeframe

Final feature outputs MUST be aligned to simulation timeframe (5m, 15m, 1h, or 4h). Source data at lower frequency (daily macro) is forward-filled. Source data at higher frequency (5m intra-bar variance when sim is 1h) is aggregated.

### Rule P2.3: No look-ahead

Computing feature at time t uses ONLY data available at time t. Forward-fill of lower-frequency data uses last known value at time t, not future values. This is critical for valid RL training.

### Rule P2.4: Validate per feature

Each feature computed runs a validation pass:
- No NaNs except at expected warmup period start
- No infinities
- Range sanity check (e.g., RSI between 0 and 100)
- Look-ahead test: feature_t cannot equal future_value_t+k

### Rule P2.5: Document every technique

Per master plan Rule M.6: every feature technique cited from published source. README per feature set explains technique with citation.

### Rule P2.6: Reuse existing infrastructure where possible

`feature-extractor` repo has autoencoders (transformer, LSTM, CNN, VAE variants). Phase 2.4 reuses these via the existing repo's plugin loading. Do NOT reimplement autoencoder code.

---

## 5. Phase 2 User Gates

After each stage, agent produces deliverable, halts, awaits user approval:

- After 2.1: User reviews resampled/aligned data structure
- After 2.2: User reviews technical + statistical feature library
- After 2.3: User reviews signal decomposition features
- After 2.4: User reviews learned representations + approves Phase 3 start

---

## 6. Phase 2 Output Structure

After Phase 2 complete, feature library structure:

```
~/Documents/financial_data/features/
├── README.md
├── trading_asset_features/
│   ├── eurusd/
│   │   ├── 5m/
│   │   │   ├── technical.parquet      (Stage 2.2 output)
│   │   │   ├── statistical.parquet    (Stage 2.2)
│   │   │   ├── wavelet.parquet        (Stage 2.3)
│   │   │   ├── hilbert.parquet        (Stage 2.3)
│   │   │   ├── multitaper.parquet     (Stage 2.3)
│   │   │   ├── emd.parquet            (Stage 2.3)
│   │   │   ├── fracdiff.parquet       (Stage 2.3)
│   │   │   ├── learned_cvae.parquet   (Stage 2.4)
│   │   │   ├── learned_lstm.parquet   (Stage 2.4)
│   │   │   └── learned_transformer.parquet (Stage 2.4)
│   │   ├── 15m/
│   │   ├── 1h/
│   │   └── 4h/
│   ├── btcusdt/
│   ├── ... (per trading asset)
└── cross_source_features/
    ├── 5m/  (all features forward-filled to 5m)
    │   ├── macro_fred.parquet
    │   ├── equity_indices.parquet
    │   ├── crypto_onchain.parquet
    │   ├── funding_rates.parquet
    │   ├── cot_positioning.parquet
    │   └── economic_calendar.parquet
    ├── 15m/
    ├── 1h/
    └── 4h/
```

This structure enables Phase 3 to combine trading asset features + cross-source features at the same simulation timeframe into the agent's observation space.

---

## 7. Approval to Begin Phase 2

User approves Phase 2 overview after Phase 1 completion approved. Agent reads `21_STAGE_2.1_DOWNSAMPLING_AND_RESAMPLING.md` and begins.
