# Stage A Screening Summary

Generated: 2026-06-17T10:26:07.153225+00:00

This is a preliminary Stage A synthesis. Per the adopted SOTA hardening gates, no configuration is promoted to Stage B until leakage, availability, DSR/PBO, baseline, and cost-sensitivity checks pass.

## Run Counts

- Total summary files: 5734
- Machines: dragon, gamma, omega
- Assets: adausdt, audusd, bnbusdt, btcusdt, btcusdt_perp, dogeusdt, ethusdt, ethusdt_perp, eurgbp, eurjpy, eurusd, gbpjpy, gbpusd, linkusdt, nzdusd, solusdt, usdcad, usdchf, usdjpy, xrpusdt
- Feature presets: baseline_12, crypto_full, fx_full, kitchen_sink_guarded, learned_cnn, learned_lstm, sota_low_cost, tech_full, tech_stat, tech_stat_decomp

## Verdict Counts

| Verdict | Runs |
| --- | ---: |
| KILL_negative_sharpe | 1310 |
| KILL_no_trades | 1198 |
| KILL_non_positive_return | 3134 |
| WATCH_preliminary_blocked_until_hardening | 92 |

## Top 20 By Total Return

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | ethusdt_perp | 15m | sac | tech_full | 0.5294 | 0.0699 | 8.11 | 198 | WATCH_preliminary_blocked_until_hardening |
| 2 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 3 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 4 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260516T053653Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 5 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 6 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 7 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 8 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T102748Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 9 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 10 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260524T104911Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 11 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T104519Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 12 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260524T091707Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 13 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 14 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260530T101542Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 15 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260605T063052Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 16 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s1_20260524T085243Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 17 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260503T192405Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 18 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s2_20260509T054549Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 19 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260524T082750Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 20 | `ethusdt_perp_4h_sac_learned_cnn_direct_atr_sltp_s0_20260503T202932Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | learned_cnn | 0.1649 | 0.0277 | 7.17 | 508 | WATCH_preliminary_blocked_until_hardening |

## Top 20 By Sharpe

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | ethusdt_perp | 15m | sac | tech_full | 0.5294 | 0.0699 | 8.11 | 198 | WATCH_preliminary_blocked_until_hardening |
| 2 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 3 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 4 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260516T053653Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 5 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 6 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 7 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 8 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T102748Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 9 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 10 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260524T104911Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 11 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T104519Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 12 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260524T091707Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 4.48 | 166 | WATCH_preliminary_blocked_until_hardening |
| 13 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 14 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260530T101542Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 15 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260605T063052Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 16 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s1_20260524T085243Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 7.17 | 498 | WATCH_preliminary_blocked_until_hardening |
| 17 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260503T192405Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 18 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s2_20260509T054549Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 19 | `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260524T082750Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | baseline_12 | 0.1675 | 0.0285 | 7.17 | 509 | WATCH_preliminary_blocked_until_hardening |
| 20 | `ethusdt_perp_4h_sac_kitchen_sink_guarded_direct_atr_sltp_s0_20260503T211134Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | kitchen_sink_guarded | 0.1588 | 0.0278 | 7.17 | 489 | WATCH_preliminary_blocked_until_hardening |

## Feature Preset Ranking

| Preset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| sota_low_cost | 342 | -0.0016 | -1041.9050 | 2.81 | 137 |
| fx_full | 310 | -0.0021 | -43.9714 | 0.31 | 28 |
| learned_cnn | 634 | -0.0021 | -717.0244 | 1.32 | 159 |
| kitchen_sink_guarded | 626 | -0.0021 | -324.7183 | 1.09 | 146 |
| baseline_12 | 714 | -0.0032 | -628.0544 | 1.19 | 171 |
| tech_full | 693 | -0.0035 | -672.6634 | 1.37 | 149 |
| tech_stat | 726 | -0.0035 | -589.5646 | 1.49 | 201 |
| learned_lstm | 665 | -0.0043 | -789.8297 | 1.47 | 166 |
| tech_stat_decomp | 691 | -0.0080 | -727.5910 | 1.57 | 141 |
| crypto_full | 333 | -0.0129 | -1342.7644 | 2.83 | 104 |

## Algorithm Ranking

| Algo | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| ppo | 1940 | -0.0025 | -898.3963 | 0.61 | 377 |
| dqn | 2047 | -0.0045 | -924.4719 | 0.99 | 582 |
| sac | 1747 | -0.0055 | -0.4670 | 3.00 | 443 |

## Asset Ranking

| Asset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| xrpusdt | 304 | 0.0007 | -1071.3464 | 0.16 | 100 |
| dogeusdt | 327 | 0.0007 | -8771.1154 | 0.12 | 174 |
| adausdt | 296 | 0.0004 | -1007.5410 | 0.34 | 133 |
| eurgbp | 318 | -0.0008 | -87.3228 | 0.09 | 49 |
| nzdusd | 257 | -0.0008 | -56.6475 | 0.11 | 28 |
| gbpusd | 235 | -0.0010 | -44.5639 | 0.24 | 24 |
| audusd | 232 | -0.0010 | -54.5640 | 0.13 | 18 |
| usdchf | 282 | -0.0011 | -58.6060 | 0.19 | 21 |
| eurusd | 250 | -0.0013 | -55.9310 | 0.17 | 9 |
| usdcad | 240 | -0.0015 | -52.7619 | 0.19 | 11 |
| bnbusdt | 285 | -0.0020 | -2.8698 | 2.06 | 99 |
| usdjpy | 253 | -0.0043 | -1.5430 | 0.53 | 10 |
| ethusdt | 307 | -0.0044 | -0.7531 | 2.23 | 100 |
| ethusdt_perp | 309 | -0.0046 | -1.2127 | 3.86 | 111 |
| eurjpy | 396 | -0.0056 | -1.1411 | 0.71 | 45 |
| gbpjpy | 217 | -0.0057 | -1.0478 | 0.93 | 36 |
| linkusdt | 268 | -0.0065 | -34.8012 | 1.86 | 92 |
| btcusdt_perp | 321 | -0.0126 | -0.1538 | 5.40 | 124 |
| btcusdt | 301 | -0.0130 | -0.1088 | 5.76 | 108 |
| solusdt | 336 | -0.0146 | -11.2869 | 2.80 | 110 |

## Machine Contribution

| Machine | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| omega | 432 | -0.0007 | -380.7869 | 1.86 | 172 |
| gamma | 2637 | -0.0022 | -816.9031 | 0.75 | 427 |
| dragon | 2665 | -0.0066 | -633.5397 | 2.13 | 803 |

## Promotion Blockers

- All candidates are currently blocked from Stage B promotion by the hardening gate.
- Required before promotion: leakage audit, availability/vintage audit, DSR/PBO-style overfit diagnostics, net-cost sensitivity, and baseline/null comparisons.
- Several high-return runs still show negative Sharpe or low trade counts; those must not be treated as validated edge.

## Deliverables

- `experiments/stage_a_screening/index.csv`
- `experiments/stage_a_screening/stage_a_summary.md`
