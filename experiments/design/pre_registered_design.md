# Project 3 Pre-Registered Experiment Design

Updated: 2026-05-02

## Objective

Measure which feature families and data sources improve RL trading performance when algorithms are held fixed.

## Initial Assets

- Crypto: `btcusdt`, `ethusdt`, `btcusdt_perp`
- FX: `eurusd`, `usdjpy`

## Initial Timeframes

- Stage A first wave: `1h`, `4h`
- Expansion wave: `15m`, then `5m` after learned-input prep is validated

## Feature Presets

| Preset | Contents |
| --- | --- |
| `baseline_12` | Minimal technical baseline from Project 2 |
| `tech_full` | Stage 2.2 technical feature set |
| `tech_stat` | Technical plus statistical features |
| `tech_stat_decomp` | Technical, statistical, and Stage 2.3 decomposition features |
| `learned_lstm` | Stage 2.4 LSTM autoencoder embeddings |
| `learned_cnn` | Stage 2.4 CNN autoencoder embeddings |
| `sota_low_cost` | HMM regimes, jump-robust realized moments, pair spreads, and funding term structure where available |
| `crypto_full` | Crypto technical, decomposition, learned, funding, and on-chain features where available |
| `fx_full` | FX technical, decomposition, learned, macro, and SOTA regime/spread features where available |
| `kitchen_sink_guarded` | All available non-leaking features, capped by feature-selection rules |

## Algorithms

Use Project 2 fixed configurations only:

- PPO
- SAC
- DQN

No hyperparameter optimization is allowed in Stage A.

## Stage A Screening

Initial matrix:

- 5 assets
- 2 timeframes
- 10 feature presets
- 3 algorithms
- 2 seeds

Expected first-wave maximum: 600 runs.

## Promotion Rule

A configuration can advance to Stage B only if it beats the baseline on validation Sharpe, drawdown, turnover sanity, and deflated-Sharpe screening.

## Held-Out Rule

2025 data is held out. Stage C evaluates each approved candidate once. No reruns after seeing held-out results.
