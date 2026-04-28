# Stage 3.1 — Experiment Framework

**Stage goal:** Design and execute systematic RL experiments varying trading asset, simulation timeframe, feature input set, and feature engineering technique. Produce evidence about which combinations yield best policies.

**Inputs:** Phase 1 + Phase 2 complete. All raw data + feature library available.

**Outputs:**
- Pre-registered experimental design
- Stage A screening results (broad, low-budget)
- Stage B validation results (top configs, high-budget)
- Stage C held-out results (single eval per candidate)

**Machine assignment (use all 3 in parallel):**
- **Dragon (RTX 4090, fastest):** Heavy training jobs, primary candidate refinement
- **Gamma (RTX 5070 Ti, fast):** Parallel training, secondary candidates
- **Omega (RTX 4070, slowest):** Light training + evaluation + reports

---

## 1. Pre-Registered Experimental Design

Before any runs, produce `experiments/design/pre_registered_design.md` with:

### 1.1 Hypotheses

| Hypothesis | Description | Test |
|------------|-------------|------|
| H1 | Including macro features improves RL policy on FX | Compare FX policies with/without forward-filled FRED |
| H2 | Including on-chain features improves RL policy on crypto | BTC/ETH with/without Glassnode + CoinMetrics features |
| H3 | Signal decomposition features (wavelet, EMD) add value over technical alone | Add wavelet/EMD to baseline |
| H4 | Learned representations (autoencoders) outperform raw features | AE embeddings vs raw feature concatenation |
| H5 | Lower simulation timeframes (5m) provide more learnable signal than higher (4h) | Compare same asset across timeframes |
| H6 | Cross-asset features (e.g., VIX for equity-correlated assets) help | Add cross-asset features |
| H7 | Tokenized observations (KMeans codes) work for transformer policies | Token vs continuous embeddings |

### 1.2 Trading asset universe

Initial scope (Stage A screening):
- BTC/USDT (primary crypto)
- ETH/USDT (secondary crypto)
- EUR/USD (primary FX)
- USD/JPY (secondary FX)

Plus 1-2 from each: GBP/USD, AUD/USD, BTCUSDT_perp.

Stage B can include more if Stage A reveals interesting candidates.

### 1.3 Simulation timeframes

All 4: 5m, 15m, 1h, 4h.

### 1.4 Feature input sets

Define discrete "feature presets" for systematic comparison:

| Preset | Description | Features included |
|--------|-------------|-------------------|
| `baseline_12` | Project 2 baseline | 12 technical features (returns, log_returns, RSI, MACD hist, BB pos, volume ratio, EMA cross, ATR norm, OBV delta, momentum_5, momentum_20, vol_20) |
| `tech_full` | All technical features | All Stage 2.2 technical features (~80 features) |
| `tech_stat` | Technical + statistical | tech_full + Stage 2.2 statistical |
| `tech_stat_decomp` | Plus signal decomposition | + Stage 2.3 wavelet + EMD + fracdiff |
| `learned_lstm` | LSTM autoencoder embedding (32-dim) | Latent vector replaces raw features |
| `learned_transformer` | Transformer AE embedding | Same |
| `learned_cvae` | CVAE embedding | Same |
| `tech_macro` | Technical + cross-asset macro | tech_full + forward-filled FRED |
| `crypto_full` | Crypto-specific full | tech_full + on-chain (Glassnode + CoinMetrics) + funding rates |
| `fx_full` | FX-specific full | tech_full + COT positioning + bond spreads + macro |
| `kitchen_sink` | Everything | All available features (high-dimensional, may overfit) |

This produces ~10 distinct feature presets per (asset, timeframe).

### 1.5 RL algorithms (held fixed)

Use Project 2 best configurations exactly. From Project 2 Part II-7 pilot results:

- **PPO** (BTC 1h technical): val Sharpe 2.4 (was buy-and-hold artifact, but algo config is solid)
- **SAC** (BTC 1h technical)
- **DQN** (BTC 1h technical)

For each (asset, timeframe, feature_preset), test ALL 3 algorithms.

### 1.6 Total experiments matrix

Stage A screening:
- 6 assets × 4 timeframes × 10 feature presets × 3 algos × 3 seeds = **2160 runs**
- Each run: ~100k timesteps (cheap, fast)
- Estimated total compute: substantial but feasible across 3 GPUs

Stage A is too large for full execution. Apply staged screening:

**Stage A reduced (more practical):**
- 4 assets × 2 timeframes (1h, 4h — biggest impact, less compute) × 10 presets × 3 algos × 2 seeds = **480 runs**
- Each ~100k timesteps

**Stage B validation:**
- Top 20 configurations from Stage A
- Each run: 1M-2M timesteps × 3 seeds = 60 jobs
- Heavy compute, but bounded

**Stage C held-out:**
- Top 5 from Stage B per asset class (crypto, FX, mixed) = 15 candidates
- Single deterministic rollout each on 2025 held-out

### 1.7 Kill criteria (Rule P3.4)

A configuration is "killed" (not promoted to Stage B) if Stage A screening shows:
- Mean validation Sharpe < 0 across seeds
- Mean validation Sharpe within ±0.1 of buy-and-hold (no edge)
- Run errors / NaN losses / training diverges

A configuration is "killed" at Stage B if:
- Mean validation Sharpe < 0.3 (per Project 2 KPI bar)
- Excessive drawdown (>30%) on validation

Kill criteria documented BEFORE runs. Post-hoc relaxation forbidden.

### 1.8 Multiple-testing correction

With 480+ Stage A runs, expect false positives. Apply:

- **Deflated Sharpe Ratio (Lopez de Prado):** account for variance + skewness + kurtosis + number of trials
- **DSR threshold:** require DSR p-value < 0.01 (stricter than 0.05) to claim significance

```python
def deflated_sharpe_ratio(observed_sharpe, n_trials, returns):
    """Lopez de Prado DSR with multiple testing correction."""
    # ... formula from Lopez de Prado (2018)
    pass
```

---

## 2. Stage A — Screening Execution

### 2.1 Run infrastructure

Reuse + extend `agent-multi/tools/seed_sweep.py` from Project 2 Part III plan.

```bash
# Per (asset, timeframe, feature_preset, algo, seed) run:
ssh dragon "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && \
  cd /home/harveybc/Documents/GitHub/agent-multi && \
  python -m agent_multi train \
    --algo ppo \
    --asset btcusdt \
    --timeframe 1h \
    --feature_preset tech_full \
    --total_timesteps 100000 \
    --seed 0 \
    --output_dir /home/harveybc/Documents/financial_data/experiments/stage_a_screening/runs/<run_id>/"
```

### 2.2 Run registry

Each run produces `summary.json` with metrics, config, git_sha. All summaries aggregate to `experiments/stage_a_screening/index.csv`.

### 2.3 Parallel execution

Distribute runs across 3 machines:
- Dragon: PPO BTC + ETH all timeframes all presets
- Gamma: SAC + DQN crypto + PPO FX
- Omega: SAC + DQN FX + parallel light jobs

Approximate parallelism: 3 jobs per machine simultaneously × 3 machines = 9 concurrent runs.

### 2.4 Stage A deliverable

`experiments/stage_a_screening/stage_a_summary.md`:

- Total runs: [N]
- Successful: [N]
- Failed: [N] with reasons
- Top 20 configs by mean validation Sharpe (with DSR correction)
- Heatmap: feature preset × asset class showing which presets work where
- Kill list: configs not promoted to Stage B and reasons

User reviews. Approves Stage B candidates.

---

## 3. Stage B — Validation Execution

### 3.1 Validation runs

For each of top 20 configs from Stage A:
- 1M-2M total_timesteps (full budget)
- 3 seeds
- d5 fitness during GA hyperparameter search if applicable
- d6 NEVER touched (held-out)

### 3.2 Validation gate

For Stage B to proceed past validation:
- Mean validation Sharpe ≥ 0.3 across 3 seeds
- Std validation Sharpe < 0.5 (i.e., not high variance)
- No degenerate policy (e.g., always-long, always-short, no-trade)

### 3.3 Stage B deliverable

`experiments/stage_b_validation/stage_b_summary.md`:

- Top 5 candidates per asset class promoted to Stage C
- Hyperparameter sensitivity analysis
- Robustness checks (across seeds, across feature subsets)

User reviews. Approves Stage C held-out test.

---

## 4. Stage C — Held-Out Execution

### 4.1 Held-out evaluation

For each Stage B winner:
- Load best policy checkpoint (best of 3 seeds by validation Sharpe)
- Single deterministic rollout on d6 = 2025-01-01 to 2025-12-31
- Compute final metrics: Sharpe, Sortino, Calmar, max DD, win rate, trade count, transaction cost ratio

### 4.2 Statistical evaluation

For each held-out result:
- Bootstrap confidence intervals (1000× trade-level resampling)
- Compare to buy-and-hold + random walk + Project 2 best result
- Apply DSR with full multiple-testing correction

### 4.3 Stage C deliverable

`experiments/stage_c_held_out/stage_c_results.md`:

- Final results table per candidate
- Statistical significance per result
- Qualitative analysis (what worked, what didn't)

User reviews. Synthesis Stage 3.2 begins.

---

## 5. Stage 3.1 Deliverable

`STAGE_3.1_DELIVERABLE.md`:

```markdown
# Stage 3.1 Deliverable — Experiment Framework

## Pre-registered design

[reference to design document]

## Stage A screening

- Total runs executed: [N]
- Top 20 configs identified
- DSR correction applied

## Stage B validation

- 20 configs full-budget tested
- Top 5 per asset class promoted

## Stage C held-out

- 15 candidates evaluated on 2025 held-out
- Statistical significance per result documented

## User Gate

User reviews. Approves Stage 3.2 (Results Synthesis) start.
```

---

## 6. User Gate

User approves moving to Stage 3.2 final synthesis.
