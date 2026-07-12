# Data Source Value Ranking

Generated: 2026-07-08T03:13:44.477136+00:00

Status: diagnostic only. Paid/source-family cancellation decisions are deferred until at least one candidate passes Stage B statistical gates.

| Source family | Runs | Matched pairs | Mean Δ return | Median Δ return | Positive pairs | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| crypto_paid_or_onchain_bundle | 381 | 253 | -0.009042 | -0.000001 | 107 | DEFER_KEEP_CANCEL_DECISION |
| derived_market_structure | 418 | 249 | 0.003292 | 0.000001 | 140 | OWN_DERIVED_BASELINE_CONTEXT |
| fx_paid_or_macro_bundle | 311 | 270 | 0.000212 | 0.000000 | 102 | DEFER_KEEP_CANCEL_DECISION |
| mixed_all_available_bundle | 672 | 516 | 0.002088 | 0.000000 | 236 | DEFER_KEEP_CANCEL_DECISION |
| own_asset_ohlcv | 5033 | 537 | 0.001363 | 0.000000 | 202 | OWN_DERIVED_BASELINE_CONTEXT |

Important: `crypto_paid_or_onchain_bundle`, `fx_paid_or_macro_bundle`, and `mixed_all_available_bundle` are preset-level bundles, not individual-vendor proof.
