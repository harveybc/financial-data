# Feature Technique Value Ranking

Generated: 2026-06-04T01:04:02.961819+00:00

Status: diagnostic only. No technique is promoted because Stage B has zero ready candidates.

| Technique / family | Runs | Matched pairs | Mean Δ return | Median Δ return | Positive pairs | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 703 | 520 | 0.000804 | 0.000000 | 222 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| cnn_autoencoder | 629 | 511 | 0.001318 | 0.000000 | 221 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| crypto_structure | 328 | 248 | -0.009207 | -0.000001 | 103 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| decomposition | 1306 | 533 | -0.000955 | 0.000000 | 224 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| fx_structure | 310 | 270 | 0.000212 | 0.000000 | 102 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| kitchen_sink_guarded | 622 | 512 | 0.002613 | 0.000000 | 235 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| learned_embeddings | 1908 | 539 | 0.001838 | 0.000000 | 235 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| lstm_autoencoder | 657 | 509 | 0.000629 | 0.000000 | 215 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| paid_or_subscription | 1260 | 537 | -0.001358 | 0.000000 | 235 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| sota_low_cost | 336 | 245 | 0.003770 | 0.000000 | 136 | DIAGNOSTIC_ONLY_BLOCKED_STAGE_B |
| statistical | 2996 | 539 | -0.001071 | 0.000000 | 223 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |
| technical | 3680 | 538 | -0.001158 | 0.000000 | 222 | NEGATIVE_OR_NEUTRAL_DIAGNOSTIC |

Interpretation: these are matched Stage A deltas by `(asset, timeframe, algo, seed)`. They are useful for triage, not final evidence.
Stage B ready candidates: 0. DSR pass/fail: 0/693.
