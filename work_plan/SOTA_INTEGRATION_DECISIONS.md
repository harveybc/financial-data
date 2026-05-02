# SOTA Integration Decisions

Updated: 2026-05-02T01:48:23.216275+00:00

## Immediate Additions

- jump-robust intrabar realized moments using existing 5m bars
- HMM market-regime labels using existing OHLC closes
- cointegration-style pair spread and z-score features
- crypto funding-rate term-structure features from existing Binance funding data

These additions are CPU-safe, use already acquired data, and produce auditable parquet deliverables under `features/trading_asset_features/<asset>/<tf>/`.

## Next Low-Cost Queue

These are now approved as next candidates, but should not interrupt active Stage 2.4 GPU jobs:

- VRP from FRED VIX plus realized variance from existing 5m bars.
- Deribit DVOL for BTC/ETH if the free endpoint is stable and provenance can be recorded.
- FX carry after validating the policy-rate mapping for EUR/USD and USD/JPY.
- Deflated Sharpe Ratio in Stage A screening; this is already required in `experiments/design/multiple_testing_correction.md`.

## Deferred Items

- PCMCI+ causal selection until Phase 3 experiment framework can validate feature selection leakage
- Decision Transformer, DreamerV3, hierarchical RL, and CQL/IQL until Phase 3 baselines are reproducible

## Validation Rule

Every new SOTA feature family must provide a metadata/report artifact and must be validated against the relevant work-plan deliverable before Phase 3 experiments consume it.
