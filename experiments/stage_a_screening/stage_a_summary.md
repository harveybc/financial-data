# Stage A Screening Summary

Generated: 2026-05-02T06:24:36.047016+00:00

This is a preliminary Stage A synthesis. Per the adopted SOTA hardening gates, no configuration is promoted to Stage B until leakage, availability, DSR/PBO, baseline, and cost-sensitivity checks pass.

## Run Counts

- Total summary files: 81
- Machines: dragon, gamma, omega
- Assets: btcusdt, ethusdt, eurusd, usdjpy
- Feature presets: baseline_12, learned_cnn, learned_lstm, sota_low_cost, tech_full, tech_stat, tech_stat_decomp

## Verdict Counts

| Verdict | Runs |
| --- | ---: |
| KILL_negative_sharpe | 22 |
| KILL_no_trades | 15 |
| KILL_non_positive_return | 43 |
| WATCH_preliminary_blocked_until_hardening | 1 |

## Top 20 By Total Return

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_stat | 0.1512 | 0.0115 | 11.11 | 426 | WATCH_preliminary_blocked_until_hardening |
| 2 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260502T043423Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 3 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260502T054241Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 4 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T045932Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 5 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s1_20260502T054034Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 6 | `btcusdt_4h_ppo_learned_cnn_direct_atr_sltp_s0_20260502T044544Z_project3_stage31_firstwave` | btcusdt | 4h | ppo | learned_cnn | 0.0484 | -0.0176 | 5.00 | 160 | KILL_negative_sharpe |
| 7 | `btcusdt_4h_dqn_tech_stat_direct_atr_sltp_s0_20260502T050641Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | tech_stat | 0.0310 | -0.0275 | 4.99 | 50 | KILL_negative_sharpe |
| 8 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s0_20260502T044650Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 9 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s1_20260502T054659Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 10 | `btcusdt_4h_sac_tech_full_direct_atr_sltp_s0_20260502T050749Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_full | 0.0157 | -0.0260 | 9.87 | 193 | KILL_negative_sharpe |
| 11 | `ethusdt_1h_sac_tech_full_direct_atr_sltp_s0_20260502T050958Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_full | 0.0107 | -0.0733 | 1.83 | 33 | KILL_negative_sharpe |
| 12 | `btcusdt_4h_dqn_learned_lstm_direct_atr_sltp_s0_20260502T045252Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | learned_lstm | 0.0059 | -0.1741 | 0.92 | 18 | KILL_negative_sharpe |
| 13 | `usdjpy_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T044028Z_project3_stage31_firstwave` | usdjpy | 4h | sac | tech_stat | 0.0035 | -0.3642 | 1.04 | 248 | KILL_negative_sharpe |
| 14 | `ethusdt_1h_dqn_baseline_12_direct_atr_sltp_s0_20260502T044439Z_project3_stage31_firstwave` | ethusdt | 1h | dqn | baseline_12 | 0.0030 | -0.3987 | 0.39 | 4671 | KILL_negative_sharpe |
| 15 | `usdjpy_4h_dqn_tech_full_direct_atr_sltp_s0_20260502T045003Z_project3_stage31_firstwave` | usdjpy | 4h | dqn | tech_full | 0.0018 | -0.5306 | 0.76 | 3277 | KILL_negative_sharpe |
| 16 | `btcusdt_4h_ppo_tech_full_direct_atr_sltp_s0_20260502T044335Z_project3_stage31_firstwave` | btcusdt | 4h | ppo | tech_full | 0.0017 | -0.0409 | 5.54 | 686 | KILL_negative_sharpe |
| 17 | `ethusdt_4h_dqn_tech_stat_direct_atr_sltp_s0_20260502T050231Z_project3_stage31_firstwave` | ethusdt | 4h | dqn | tech_stat | 0.0013 | -0.6389 | 0.39 | 61 | KILL_negative_sharpe |
| 18 | `ethusdt_4h_ppo_tech_stat_direct_atr_sltp_s0_20260502T045828Z_project3_stage31_firstwave` | ethusdt | 4h | ppo | tech_stat | 0.0006 | -0.4974 | 0.35 | 733 | KILL_negative_sharpe |
| 19 | `ethusdt_4h_dqn_baseline_12_direct_atr_sltp_s0_20260502T043424Z_project3_stage31_firstwave` | ethusdt | 4h | dqn | baseline_12 | 0.0004 | -0.5821 | 0.55 | 474 | KILL_negative_sharpe |
| 20 | `ethusdt_1h_dqn_tech_stat_direct_atr_sltp_s0_20260502T045714Z_project3_stage31_firstwave` | ethusdt | 1h | dqn | tech_stat | 0.0001 | -0.5012 | 0.43 | 1235 | KILL_negative_sharpe |

## Top 20 By Sharpe

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_stat | 0.1512 | 0.0115 | 11.11 | 426 | WATCH_preliminary_blocked_until_hardening |
| 2 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260502T043423Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 3 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260502T054241Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 4 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T045932Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 5 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s1_20260502T054034Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 6 | `btcusdt_4h_ppo_learned_cnn_direct_atr_sltp_s0_20260502T044544Z_project3_stage31_firstwave` | btcusdt | 4h | ppo | learned_cnn | 0.0484 | -0.0176 | 5.00 | 160 | KILL_negative_sharpe |
| 7 | `btcusdt_4h_sac_tech_full_direct_atr_sltp_s0_20260502T050749Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_full | 0.0157 | -0.0260 | 9.87 | 193 | KILL_negative_sharpe |
| 8 | `btcusdt_4h_dqn_tech_stat_direct_atr_sltp_s0_20260502T050641Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | tech_stat | 0.0310 | -0.0275 | 4.99 | 50 | KILL_negative_sharpe |
| 9 | `ethusdt_4h_sac_baseline_12_direct_atr_sltp_s0_20260502T044025Z_project3_stage31_firstwave` | ethusdt | 4h | sac | baseline_12 | -0.1353 | -0.0398 | 19.96 | 752 | KILL_non_positive_return |
| 10 | `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s1_20260502T053631Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_stat | -0.1312 | -0.0400 | 19.96 | 733 | KILL_non_positive_return |
| 11 | `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s2_20260502T053827Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_stat | -0.1312 | -0.0400 | 19.96 | 733 | KILL_non_positive_return |
| 12 | `btcusdt_4h_ppo_tech_full_direct_atr_sltp_s0_20260502T044335Z_project3_stage31_firstwave` | btcusdt | 4h | ppo | tech_full | 0.0017 | -0.0409 | 5.54 | 686 | KILL_negative_sharpe |
| 13 | `btcusdt_4h_dqn_baseline_12_direct_atr_sltp_s0_20260502T042820Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | baseline_12 | -0.0258 | -0.0410 | 6.02 | 1117 | KILL_non_positive_return |
| 14 | `btcusdt_4h_dqn_baseline_12_direct_atr_sltp_s0_20260502T042926Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | baseline_12 | -0.0258 | -0.0410 | 6.02 | 1117 | KILL_non_positive_return |
| 15 | `ethusdt_4h_sac_tech_full_direct_atr_sltp_s0_20260502T050519Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_full | -0.1379 | -0.0413 | 19.96 | 740 | KILL_non_positive_return |
| 16 | `btcusdt_1h_ppo_tech_stat_direct_atr_sltp_s0_20260502T050336Z_project3_stage31_firstwave` | btcusdt | 1h | ppo | tech_stat | -0.0106 | -0.0466 | 3.50 | 2577 | KILL_non_positive_return |
| 17 | `btcusdt_1h_dqn_tech_stat_decomp_direct_atr_sltp_s0_20260502T043848Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_stat_decomp | -0.0177 | -0.0494 | 3.76 | 1644 | KILL_non_positive_return |
| 18 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s0_20260502T044650Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 19 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s1_20260502T054659Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 20 | `btcusdt_1h_dqn_tech_stat_direct_atr_sltp_s0_20260502T045936Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_stat | -0.0280 | -0.0560 | 5.11 | 1578 | KILL_non_positive_return |

## Feature Preset Ranking

| Preset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| learned_cnn | 1 | 0.0484 | -0.0176 | 5.00 | 1 |
| sota_low_cost | 3 | 0.0470 | -0.0763 | 7.37 | 2 |
| tech_stat | 24 | 0.0033 | -8.0216 | 3.97 | 11 |
| learned_lstm | 9 | 0.0005 | -21.4274 | 0.16 | 1 |
| tech_stat_decomp | 4 | -0.0078 | -15.7559 | 1.40 | 0 |
| tech_full | 21 | -0.0079 | -8.1412 | 2.17 | 4 |
| baseline_12 | 19 | -0.0165 | -23.4236 | 3.15 | 4 |

## Algorithm Ranking

| Algo | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| sac | 22 | -0.0007 | -0.2234 | 6.97 | 10 |
| ppo | 35 | -0.0034 | -24.2158 | 1.29 | 4 |
| dqn | 24 | -0.0042 | -11.9401 | 1.52 | 9 |

## Asset Ranking

| Asset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| btcusdt | 22 | 0.0090 | -0.0717 | 5.23 | 9 |
| eurusd | 18 | -0.0004 | -63.9010 | 0.07 | 3 |
| usdjpy | 21 | -0.0046 | -0.6399 | 0.78 | 2 |
| ethusdt | 20 | -0.0164 | -0.2833 | 5.11 | 9 |

## Machine Contribution

| Machine | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| dragon | 29 | -0.0017 | -0.1132 | 6.33 | 13 |
| gamma | 27 | -0.0033 | -17.8777 | 0.49 | 1 |
| omega | 25 | -0.0039 | -21.8023 | 1.52 | 9 |

## Promotion Blockers

- All candidates are currently blocked from Stage B promotion by the hardening gate.
- Required before promotion: leakage audit, availability/vintage audit, DSR/PBO-style overfit diagnostics, net-cost sensitivity, and baseline/null comparisons.
- Several high-return runs still show negative Sharpe or low trade counts; those must not be treated as validated edge.

## Deliverables

- `experiments/stage_a_screening/index.csv`
- `experiments/stage_a_screening/stage_a_summary.md`
