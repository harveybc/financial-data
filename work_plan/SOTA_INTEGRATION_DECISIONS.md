# SOTA Integration Decisions

Updated: 2026-05-02T04:55:00+00:00

## Adopted SOTA Hardening Package

The critique in `work_plan/PROJECT3_SOTA_CRITIQUE_AND_IMPROVEMENT_PROPOSAL.md` is accepted as a serious additive review. The most important changes are methodological safeguards, not extra model complexity.

P0 additions now required before Stage B promotion:

- immutable experiment ledger and promotion registry (`artifacts/run_ledger.jsonl`, `artifacts/run_ledger.parquet`, `configs/experiment_registry.schema.json`)
- availability/vintage/staleness contract for cross-source features (`features/AVAILABILITY_CONTRACT.md`)
- fitted-transform and held-out leakage audit (`experiments/design/leakage_audit.md`)
- transaction-cost scenario matrix (`experiments/design/cost_model.md`)
- machine-readable cost scenarios (`configs/cost_scenarios.yaml`)
- null/simple/supervised baseline comparisons in Stage A/B/C summaries
- feature-family ablation and marginal contribution scoring (`experiments/design/feature_family_ablation_plan.md`)
- paired source-family / feature-family marginal value tests matched on asset, timeframe, algorithm, seed, split, and cost scenario
- DSR plus seed variance, RL uncertainty summaries, PBO/CSCV-style diagnostics, and Reality Check / SPA-style family tests where feasible
- Stage B promotion gate (`experiments/design/stage_b_promotion_gate.yaml`)

Active Stage A jobs may continue as infrastructure smoke and preliminary evidence. They are not eligible for Stage B promotion until the new hardening gates pass.

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
- macro release staleness features: `bars_since_release`, `source_is_stale`, and conservative release lag policy
- supervised diagnostic baseline for feature-family predictive value
- paid-data shadow trials: CryptoQuant versus free crypto stack, FxMacroData versus ALFRED/FRED/CFTC/official-calendar baseline

## Deferred Items

- PCMCI+ causal selection until Phase 3 experiment framework can validate feature selection leakage
- Decision Transformer, DreamerV3, hierarchical RL, and CQL/IQL until Phase 3 baselines are reproducible
- TradingAgents multi-agent LLM strategy committee until Stage 3.1 baseline RL evidence exists. Use `work_plan/TRADINGAGENTS_INTEGRATION_ASSESSMENT.md` as the integration plan; evaluate it as an RL-signal overlay/veto layer, not as a replacement for pre-registered RL screening.
- live-only Binance order-book snapshots until a separate live/recent lane is created; never synthesize historical LOB from OHLCV
- time-series foundation models until the core PPO/SAC/DQN evidence stack is reproducible

## Validation Rule

Every new SOTA feature family must provide a metadata/report artifact and must be validated against the relevant work-plan deliverable before Phase 3 experiments consume it.
