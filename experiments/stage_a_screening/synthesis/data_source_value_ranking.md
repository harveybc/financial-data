# Data Source Value Ranking

Generated: 2026-06-04T01:04:02.990726+00:00

Status: diagnostic only. Paid/source-family cancellation decisions are deferred until at least one candidate passes Stage B statistical gates.

| Source family | Runs | Matched pairs | Mean Δ return | Median Δ return | Positive pairs | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| crypto_paid_or_onchain_bundle | 328 | 248 | -0.009207 | -0.000001 | 103 | DEFER_KEEP_CANCEL_DECISION |
| derived_market_structure | 336 | 245 | 0.003770 | 0.000000 | 136 | OWN_DERIVED_BASELINE_CONTEXT |
| fx_paid_or_macro_bundle | 310 | 270 | 0.000212 | 0.000000 | 102 | DEFER_KEEP_CANCEL_DECISION |
| mixed_all_available_bundle | 622 | 512 | 0.002613 | 0.000000 | 235 | DEFER_KEEP_CANCEL_DECISION |
| own_asset_ohlcv | 4409 | 537 | 0.001358 | 0.000000 | 208 | OWN_DERIVED_BASELINE_CONTEXT |

Important: `crypto_paid_or_onchain_bundle`, `fx_paid_or_macro_bundle`, and `mixed_all_available_bundle` are preset-level bundles, not individual-vendor proof.
