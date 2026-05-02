# Stage 2 SOTA Feature Enrichment - Omega

Generated: 2026-05-02T01:48:23.216275+00:00

- Jobs ok: 42
- Jobs failed: 0

## Applied Now

- jump-robust intrabar realized moments using existing 5m bars
- HMM market-regime labels using existing OHLC closes
- cointegration-style pair spread and z-score features
- crypto funding-rate term-structure features from existing Binance funding data

## Deferred

- VRP and DVOL until options/implied-volatility feeds are acquired
- FX carry until a full currency policy-rate mapping is validated
- PCMCI+ causal selection until Phase 3 experiment framework can validate feature selection leakage
- Decision Transformer, DreamerV3, hierarchical RL, and CQL/IQL until Phase 3 baselines are reproducible

## Outputs

| Feature Set | Asset/Pair | TF | Rows | Columns | Path |
| --- | --- | --- | ---: | ---: | --- |
| intrabar_realized | btcusdt | 1h | 73263 | 14 | `features/trading_asset_features/btcusdt/1h/sota_intrabar_realized.parquet` |
| hmm_regime | btcusdt | 1h | 73268 | 6 | `features/trading_asset_features/btcusdt/1h/sota_hmm_regime.parquet` |
| funding_term_structure | btcusdt | 1h | 73284 | 8 | `features/trading_asset_features/btcusdt/1h/sota_funding_term_structure.parquet` |
| intrabar_realized | btcusdt | 4h | 18329 | 14 | `features/trading_asset_features/btcusdt/4h/sota_intrabar_realized.parquet` |
| hmm_regime | btcusdt | 4h | 18327 | 6 | `features/trading_asset_features/btcusdt/4h/sota_hmm_regime.parquet` |
| funding_term_structure | btcusdt | 4h | 18337 | 8 | `features/trading_asset_features/btcusdt/4h/sota_funding_term_structure.parquet` |
| intrabar_realized | ethusdt | 1h | 73263 | 14 | `features/trading_asset_features/ethusdt/1h/sota_intrabar_realized.parquet` |
| hmm_regime | ethusdt | 1h | 73268 | 6 | `features/trading_asset_features/ethusdt/1h/sota_hmm_regime.parquet` |
| funding_term_structure | ethusdt | 1h | 73284 | 8 | `features/trading_asset_features/ethusdt/1h/sota_funding_term_structure.parquet` |
| intrabar_realized | ethusdt | 4h | 18329 | 14 | `features/trading_asset_features/ethusdt/4h/sota_intrabar_realized.parquet` |
| hmm_regime | ethusdt | 4h | 18327 | 6 | `features/trading_asset_features/ethusdt/4h/sota_hmm_regime.parquet` |
| funding_term_structure | ethusdt | 4h | 18337 | 8 | `features/trading_asset_features/ethusdt/4h/sota_funding_term_structure.parquet` |
| intrabar_realized | btcusdt_perp | 1h | 55350 | 14 | `features/trading_asset_features/btcusdt_perp/1h/sota_intrabar_realized.parquet` |
| hmm_regime | btcusdt_perp | 1h | 55335 | 6 | `features/trading_asset_features/btcusdt_perp/1h/sota_hmm_regime.parquet` |
| funding_term_structure | btcusdt_perp | 1h | 55351 | 8 | `features/trading_asset_features/btcusdt_perp/1h/sota_funding_term_structure.parquet` |
| intrabar_realized | btcusdt_perp | 4h | 13838 | 14 | `features/trading_asset_features/btcusdt_perp/4h/sota_intrabar_realized.parquet` |
| hmm_regime | btcusdt_perp | 4h | 13828 | 6 | `features/trading_asset_features/btcusdt_perp/4h/sota_hmm_regime.parquet` |
| funding_term_structure | btcusdt_perp | 4h | 13838 | 8 | `features/trading_asset_features/btcusdt_perp/4h/sota_funding_term_structure.parquet` |
| intrabar_realized | eurusd | 1h | 129491 | 13 | `features/trading_asset_features/eurusd/1h/sota_intrabar_realized.parquet` |
| hmm_regime | eurusd | 1h | 129857 | 6 | `features/trading_asset_features/eurusd/1h/sota_hmm_regime.parquet` |
| intrabar_realized | eurusd | 4h | 32595 | 13 | `features/trading_asset_features/eurusd/4h/sota_intrabar_realized.parquet` |
| hmm_regime | eurusd | 4h | 33753 | 6 | `features/trading_asset_features/eurusd/4h/sota_hmm_regime.parquet` |
| intrabar_realized | usdjpy | 1h | 129470 | 13 | `features/trading_asset_features/usdjpy/1h/sota_intrabar_realized.parquet` |
| hmm_regime | usdjpy | 1h | 129836 | 6 | `features/trading_asset_features/usdjpy/1h/sota_hmm_regime.parquet` |
| intrabar_realized | usdjpy | 4h | 32593 | 13 | `features/trading_asset_features/usdjpy/4h/sota_intrabar_realized.parquet` |
| hmm_regime | usdjpy | 4h | 33748 | 6 | `features/trading_asset_features/usdjpy/4h/sota_hmm_regime.parquet` |
| pair_spread | btcusdt/ethusdt | 1h | 73284 |  |  |
| pair_spread | btcusdt/btcusdt_perp | 1h | 55315 |  |  |
| pair_spread | eurusd/usdjpy | 1h | 129411 |  |  |
| pair_spread | btcusdt/ethusdt | 4h | 18337 |  |  |
| pair_spread | btcusdt/btcusdt_perp | 4h | 13837 |  |  |
| pair_spread | eurusd/usdjpy | 4h | 33751 |  |  |
| pair_spread_output |  |  | 73284 | 9 | `features/trading_asset_features/btcusdt/1h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 18337 | 9 | `features/trading_asset_features/btcusdt/4h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 55315 | 5 | `features/trading_asset_features/btcusdt_perp/1h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 13837 | 5 | `features/trading_asset_features/btcusdt_perp/4h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 73284 | 5 | `features/trading_asset_features/ethusdt/1h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 18337 | 5 | `features/trading_asset_features/ethusdt/4h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 129411 | 5 | `features/trading_asset_features/eurusd/1h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 33751 | 5 | `features/trading_asset_features/eurusd/4h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 129411 | 5 | `features/trading_asset_features/usdjpy/1h/sota_pair_spreads.parquet` |
| pair_spread_output |  |  | 33751 | 5 | `features/trading_asset_features/usdjpy/4h/sota_pair_spreads.parquet` |
