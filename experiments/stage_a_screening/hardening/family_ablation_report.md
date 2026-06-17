# Stage 3.1 B9 Feature-Family Ablation Report

Generated: 2026-05-10T04:19:33.354351+00:00

## Summary

- Runs with B9 status: 4928
- Matched comparison rows: 8283
- Missing/not-applicable rows: 905

| B9 evidence | Count |
| --- | ---: |
| BLOCKED_NO_MATCH | 167 |
| FAIL | 2319 |
| INDETERMINATE | 241 |
| NOT_APPLICABLE | 612 |
| PARTIAL_PASS | 426 |
| PASS | 1163 |

| Comparison status | Count |
| --- | ---: |
| FAIL | 5197 |
| PARTIAL_PASS | 309 |
| PASS | 2777 |

## Best Run

`ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave`

- B9 evidence: **PASS**
- Reason: all required matched family ablations pass
- Matched comparisons: 2
- Best base-cost delta: 0.273904

| Family | Comparison | Ablation preset | Status | Delta base | Delta pessimistic | Delta Sharpe |
| --- | --- | --- | --- | ---: | ---: | ---: |
| statistical | statistical_increment_vs_technical | tech_full | PASS | 0.273904 | 0.246150 | 0.052854 |
| technical_statistical | technical_statistical_vs_base | baseline_12 | PASS | 0.271318 | 0.243567 | 0.051359 |

## Family Value Ranking

| Family | Asset class | Matched runs | Pass | Partial | Fail | Mean delta base | Mean delta Sharpe | Mean delta DD | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| crypto_full_stack | crypto | 235 | 86 | 15 | 134 | -0.009656 | 1058.029300 | 1.022190 | MIXED |
| crypto_structure | crypto | 228 | 93 | 14 | 121 | -0.010404 | 1150.252863 | 0.635656 | MIXED |
| decomposition | crypto | 230 | 84 | 11 | 135 | -0.015160 | -1390.544019 | 0.831723 | MIXED |
| decomposition | fx | 350 | 101 | 9 | 240 | 0.000445 | 0.883259 | -0.005227 | MIXED |
| fx_full_stack | fx | 302 | 84 | 4 | 214 | 0.000698 | -3.863215 | -0.066779 | MIXED |
| fx_macro_structure | fx | 304 | 109 | 7 | 188 | 0.000871 | -2.585670 | -0.044585 | MIXED |
| kitchen_sink_guarded_increment | crypto | 454 | 199 | 22 | 233 | 0.009243 | 64.192708 | -0.797191 | MIXED |
| kitchen_sink_guarded_increment | fx | 599 | 144 | 5 | 450 | 0.000050 | 1.479803 | -0.012847 | MIXED |
| kitchen_sink_guarded_stack | crypto | 234 | 110 | 17 | 107 | 0.005445 | -61.221932 | -0.176704 | MIXED |
| kitchen_sink_guarded_stack | fx | 301 | 83 | 6 | 212 | 0.000350 | -3.818853 | -0.057195 | MIXED |
| learned_cnn_stack | crypto | 239 | 105 | 11 | 123 | 0.000939 | -89.490118 | -0.064088 | MIXED |
| learned_cnn_stack | fx | 301 | 89 | 4 | 208 | 0.000500 | -2.787541 | -0.060480 | MIXED |
| learned_embeddings_cnn | crypto | 225 | 90 | 13 | 122 | -0.002509 | -29.408588 | -0.283595 | MIXED |
| learned_embeddings_cnn | fx | 303 | 79 | 3 | 221 | 0.000355 | 1.692968 | -0.001576 | MIXED |
| learned_embeddings_lstm | crypto | 233 | 88 | 15 | 130 | -0.003182 | 43.719849 | -0.328064 | MIXED |
| learned_embeddings_lstm | fx | 313 | 85 | 3 | 225 | 0.000550 | 1.172604 | 0.037580 | MIXED |
| learned_lstm_stack | crypto | 242 | 106 | 12 | 124 | 0.001162 | -21.814271 | -0.070361 | MIXED |
| learned_lstm_stack | fx | 312 | 94 | 5 | 213 | 0.000726 | -3.082767 | -0.018273 | MIXED |
| sota_low_cost_additions | crypto | 230 | 12 | 1 | 217 | -0.000548 | -4.169153 | 0.038931 | MIXED |
| sota_low_cost_stack | crypto | 236 | 107 | 14 | 115 | 0.004747 | -74.306066 | 0.226854 | MIXED |
| statistical | crypto | 233 | 106 | 12 | 115 | 0.003737 | -22.591411 | -0.179034 | MIXED |
| statistical | fx | 376 | 118 | 22 | 236 | 0.000368 | -1.719834 | -0.002444 | MIXED |
| technical | crypto | 238 | 103 | 16 | 119 | 0.002297 | -65.960266 | 0.430542 | MIXED |
| technical | fx | 363 | 97 | 13 | 253 | -0.000093 | -6.323095 | -0.045252 | MIXED |
| technical_statistical | crypto | 242 | 113 | 12 | 117 | 0.007164 | -63.921710 | 0.239635 | MIXED |
| technical_statistical | fx | 374 | 107 | 17 | 250 | 0.000289 | -3.792805 | -0.048949 | MIXED |
| technical_statistical_decomposition | crypto | 236 | 90 | 13 | 133 | -0.009738 | -1483.058427 | 1.001772 | MIXED |
| technical_statistical_decomposition | fx | 350 | 95 | 13 | 242 | 0.000528 | -3.253264 | -0.058426 | MIXED |

## Caveats

- This is matched Stage A evidence only; it does not replace Stage B retraining.
- Comparisons are valid only for same asset, timeframe, algorithm, and seed.
- For learned embeddings, the comparison is against `tech_stat` when available; those presets may replace rather than strictly add raw features.
- `kitchen_sink_guarded` is exploratory unless direct ablation evidence supports it.
