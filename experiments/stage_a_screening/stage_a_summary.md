# Stage A Screening Summary

Generated: 2026-07-08T19:58:11.581325+00:00

This is a preliminary Stage A synthesis. Per the adopted SOTA hardening gates, no configuration is promoted to Stage B until leakage, availability, DSR/PBO, baseline, and cost-sensitivity checks pass.

## Run Counts

- Total summary files: 6397
- Machines: dragon, gamma, omega
- Assets: adausdt, audusd, bnbusdt, btcusdt, btcusdt_perp, dogeusdt, ethusdt, ethusdt_perp, eurgbp, eurjpy, eurusd, gbpjpy, gbpusd, linkusdt, nzdusd, solusdt, usdcad, usdchf, usdjpy, xrpusdt
- Feature presets: baseline_12, crypto_full, fx_full, kitchen_sink_guarded, learned_cnn, learned_lstm, sota_low_cost, tech_full, tech_stat, tech_stat_decomp

## Verdict Counts

| Verdict | Runs |
| --- | ---: |
| KILL_negative_sharpe | 1596 |
| KILL_no_trades | 1213 |
| KILL_non_positive_return | 3458 |
| WATCH_preliminary_blocked_until_hardening | 130 |

## Top 20 By Total Return

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | ethusdt_perp | 15m | sac | tech_full | 0.5294 | 0.0699 | 8.11 | 198 | WATCH_preliminary_blocked_until_hardening |
| 2 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 3 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260704T150341Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 4 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 5 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260516T053653Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 6 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260705T121836Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 7 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 8 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260704T140312Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 9 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 10 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260704T140742Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 11 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 12 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T102748Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 13 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 14 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260705T114308Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 15 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260524T104911Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 16 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T104519Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 17 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260524T091707Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 18 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 19 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260530T101542Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 20 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260605T063052Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |

## Top 20 By Sharpe

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | ethusdt_perp | 15m | sac | tech_full | 0.5294 | 0.0699 | 8.11 | 198 | WATCH_preliminary_blocked_until_hardening |
| 2 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 3 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260704T150341Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 4 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 5 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260516T053653Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 6 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260705T121836Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 7 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 8 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260704T140312Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 9 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 10 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260704T140742Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 11 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 12 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T102748Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 13 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 14 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260705T114308Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 15 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260524T104911Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 16 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T104519Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 17 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260524T091707Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 18 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 19 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260530T101542Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 20 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260605T063052Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |

## Feature Preset Ranking

| Preset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| learned_cnn | 715 | -0.0011 | -679.8145 | 1.40 | 202 |
| fx_full | 311 | -0.0021 | -43.9388 | 0.31 | 28 |
| sota_low_cost | 418 | -0.0023 | -880.4299 | 2.99 | 172 |
| baseline_12 | 807 | -0.0025 | -605.9923 | 1.29 | 213 |
| kitchen_sink_guarded | 672 | -0.0026 | -320.3639 | 1.18 | 165 |
| tech_full | 768 | -0.0027 | -643.7606 | 1.44 | 189 |
| tech_stat | 816 | -0.0032 | -612.3052 | 1.57 | 252 |
| learned_lstm | 740 | -0.0035 | -775.3919 | 1.50 | 204 |
| tech_stat_decomp | 769 | -0.0087 | -1137.9819 | 1.73 | 176 |
| crypto_full | 381 | -0.0118 | -1197.1315 | 2.79 | 125 |

## Algorithm Ranking

| Algo | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| ppo | 2181 | -0.0022 | -1063.2232 | 0.64 | 505 |
| dqn | 2348 | -0.0040 | -850.8073 | 1.08 | 721 |
| sac | 1868 | -0.0055 | -0.4466 | 3.29 | 500 |

## Asset Ranking

| Asset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| xrpusdt | 337 | 0.0007 | -1172.3615 | 0.14 | 120 |
| dogeusdt | 403 | 0.0006 | -8255.9076 | 0.12 | 215 |
| adausdt | 341 | 0.0003 | -1020.2257 | 0.30 | 154 |
| eurgbp | 320 | -0.0008 | -87.5327 | 0.09 | 49 |
| nzdusd | 257 | -0.0008 | -56.6475 | 0.11 | 28 |
| gbpusd | 237 | -0.0009 | -44.4057 | 0.24 | 24 |
| audusd | 232 | -0.0010 | -54.5640 | 0.13 | 18 |
| usdchf | 282 | -0.0011 | -58.6060 | 0.19 | 21 |
| eurusd | 250 | -0.0013 | -55.9310 | 0.17 | 9 |
| usdcad | 241 | -0.0015 | -52.8372 | 0.19 | 11 |
| bnbusdt | 366 | -0.0015 | -4.7047 | 1.62 | 135 |
| ethusdt_perp | 390 | -0.0026 | -1.4594 | 4.00 | 153 |
| usdjpy | 253 | -0.0043 | -1.5430 | 0.53 | 10 |
| ethusdt | 373 | -0.0049 | -0.8377 | 2.10 | 123 |
| linkusdt | 311 | -0.0056 | -35.0613 | 1.60 | 109 |
| eurjpy | 396 | -0.0056 | -1.1411 | 0.71 | 45 |
| gbpjpy | 217 | -0.0057 | -1.0478 | 0.93 | 36 |
| btcusdt_perp | 416 | -0.0102 | -0.1277 | 5.72 | 175 |
| btcusdt | 356 | -0.0110 | -0.0966 | 5.85 | 145 |
| solusdt | 419 | -0.0129 | -10.1767 | 2.57 | 146 |

## Machine Contribution

| Machine | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| omega | 637 | -0.0018 | -365.9314 | 2.28 | 280 |
| gamma | 2775 | -0.0019 | -921.6247 | 0.80 | 492 |
| dragon | 2985 | -0.0061 | -628.7162 | 2.14 | 954 |

## Promotion Blockers

- All candidates are currently blocked from Stage B promotion by the hardening gate.
- Required before promotion: leakage audit, availability/vintage audit, DSR/PBO-style overfit diagnostics, net-cost sensitivity, and baseline/null comparisons.
- Several high-return runs still show negative Sharpe or low trade counts; those must not be treated as validated edge.

## Deliverables

- `experiments/stage_a_screening/index.csv`
- `experiments/stage_a_screening/stage_a_summary.md`
