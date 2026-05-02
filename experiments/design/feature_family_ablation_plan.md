# Feature-Family Ablation Plan

Updated: 2026-05-02

## Purpose

Stage A must answer which data and feature families add marginal value. A single all-feature policy cannot explain source value, subscription value, or whether a technique generalizes. This plan makes family-level attribution a first-class deliverable.

## Core Families

| Family id | Includes | Eligible assets | Promotion hypothesis |
| --- | --- | --- | --- |
| `base` | OHLCV, returns, causal rolling volatility, `baseline_12` | All | Minimum benchmark |
| `technical_statistical` | `technical.parquet`, `statistical.parquet` | All | Improves over base without excessive turnover |
| `decomposition` | Wavelet, Hilbert, multitaper, EMD, fracdiff | All | Adds robust signal beyond technical/statistical |
| `learned_embeddings` | LSTM/CNN autoencoder embeddings with leakage metadata | Assets/timeframes with valid embeddings | Compresses useful nonlinear state |
| `macro_risk` | FRED/BLS/BEA/OECD/Treasury, VIX/VRP, release proxies | FX and cross-asset context | Adds regime/risk information |
| `crypto_structure` | Funding term structure, perp basis, on-chain, DeFi, mempool | Crypto and perpetuals | Captures leverage and network positioning |
| `fx_structure` | Carry, momentum, PPP/value, COT | FX | Captures structural FX factors |
| `cross_asset_context` | Equity indices, commodities, ETFs, bonds, EM FX | All as context | Adds global risk context |
| `paid_or_subscription` | CryptoQuant, FxMacroData, or other paid data | Source-specific | Must prove marginal value after costs |
| `all_free_features` | All validated free live-equivalent families | All | Upper bound for free-data stack |
| `kitchen_sink_guarded` | All non-leaking families after caps/guards | All | Exploratory only unless ablations support it |

## Stage A Order

1. Run `base` and `technical_statistical`.
2. Add one family at a time: decomposition, learned embeddings, macro/risk, crypto structure, FX structure.
3. Test the best family pairs per asset class.
4. Test `all_free_features`.
5. Test paid-source additions only against the best free baseline.
6. Test `kitchen_sink_guarded` only as an exploratory upper bound.

## Required Metrics

For each family comparison, report:

```text
matched_asset
matched_timeframe
matched_algorithm
matched_seed_count
delta_net_sharpe_base_cost
delta_max_drawdown
delta_turnover
delta_dsr_or_adjusted_rank
seed_std
regime_sliced_delta
subscription_mapping_if_any
verdict
```

## Subscription Rule

Paid data must be judged by marginal contribution:

- `best_free_stack` versus `best_free_stack + paid_family`
- same asset/timeframe/algo/seed where feasible
- base and pessimistic cost scenarios
- no promotion if gains vanish after costs or depend on one seed
