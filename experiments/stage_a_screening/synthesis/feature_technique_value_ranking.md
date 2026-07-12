# Feature Technique Value Ranking

Generated: 2026-07-08T03:13:44.444053+00:00

Status: diagnostic only. No technique is promoted because Stage B has zero ready candidates.

| Technique / family | Runs | Matched pairs | Mean Δ return | Median Δ return | Positive pairs | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 807 | 522 | 0.001043 | 0.000000 | 222 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| cnn_autoencoder | 715 | 514 | 0.001663 | 0.000000 | 219 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| crypto_structure | 381 | 253 | -0.009042 | -0.000001 | 107 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| decomposition | 1441 | 535 | -0.001540 | 0.000000 | 228 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| fx_structure | 311 | 270 | 0.000212 | 0.000000 | 102 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| kitchen_sink_guarded | 672 | 516 | 0.002088 | 0.000000 | 236 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| learned_embeddings | 2127 | 539 | 0.001912 | 0.000000 | 229 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| lstm_autoencoder | 740 | 513 | 0.000881 | 0.000000 | 212 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| paid_or_subscription | 1364 | 537 | -0.001363 | 0.000000 | 241 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| sota_low_cost | 418 | 249 | 0.003292 | 0.000001 | 140 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| statistical | 3367 | 539 | -0.001530 | 0.000000 | 218 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| technical | 4135 | 538 | -0.001545 | 0.000000 | 222 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |

Interpretation: these are matched Stage A deltas by `(asset, timeframe, algo, seed)`. They are useful for triage, not final evidence.
Stage B ready candidates: 0. DSR pass/fail: 0/693.
