# Stage A Screening Summary

Generated: 2026-05-02T19:05:45.697277+00:00

This is a preliminary Stage A synthesis. Per the adopted SOTA hardening gates, no configuration is promoted to Stage B until leakage, availability, DSR/PBO, baseline, and cost-sensitivity checks pass.

## Run Counts

- Total summary files: 356
- Machines: dragon, gamma, omega
- Assets: audusd, btcusdt, ethusdt, eurgbp, eurusd, gbpusd, nzdusd, usdcad, usdchf, usdjpy
- Feature presets: baseline_12, crypto_full, fx_full, kitchen_sink_guarded, learned_cnn, learned_lstm, sota_low_cost, tech_full, tech_stat, tech_stat_decomp

## Verdict Counts

| Verdict | Runs |
| --- | ---: |
| KILL_negative_sharpe | 66 |
| KILL_no_trades | 50 |
| KILL_non_positive_return | 239 |
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
| 7 | `btcusdt_1h_sac_baseline_12_direct_atr_sltp_s0_20260502T103918Z_project3_stage31_firstwave` | btcusdt | 1h | sac | baseline_12 | 0.0443 | -0.0368 | 1.80 | 220 | KILL_negative_sharpe |
| 8 | `btcusdt_1h_sac_baseline_12_direct_atr_sltp_s1_20260502T104342Z_project3_stage31_firstwave` | btcusdt | 1h | sac | baseline_12 | 0.0443 | -0.0368 | 1.80 | 220 | KILL_negative_sharpe |
| 9 | `btcusdt_1h_dqn_tech_full_direct_atr_sltp_s1_20260502T110912Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_full | 0.0379 | -0.0251 | 4.98 | 5 | KILL_negative_sharpe |
| 10 | `btcusdt_15m_dqn_sota_low_cost_direct_atr_sltp_s1_20260502T093842Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | sota_low_cost | 0.0379 | -0.0252 | 4.99 | 128 | KILL_negative_sharpe |
| 11 | `btcusdt_15m_dqn_tech_stat_direct_atr_sltp_s1_20260502T074824Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | tech_stat | 0.0379 | -0.0252 | 4.99 | 128 | KILL_negative_sharpe |
| 12 | `btcusdt_1h_dqn_tech_stat_direct_atr_sltp_s0_20260502T112334Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_stat | 0.0369 | -0.0254 | 4.98 | 40 | KILL_negative_sharpe |
| 13 | `btcusdt_15m_dqn_tech_full_direct_atr_sltp_s0_20260502T071926Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | tech_full | 0.0313 | -0.0270 | 5.02 | 594 | KILL_negative_sharpe |
| 14 | `btcusdt_4h_dqn_tech_stat_direct_atr_sltp_s0_20260502T050641Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | tech_stat | 0.0310 | -0.0275 | 4.99 | 50 | KILL_negative_sharpe |
| 15 | `btcusdt_15m_dqn_baseline_12_direct_atr_sltp_s0_20260502T065236Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | baseline_12 | 0.0300 | -0.0285 | 5.02 | 621 | KILL_negative_sharpe |
| 16 | `btcusdt_1h_dqn_baseline_12_direct_atr_sltp_s1_20260502T105341Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | baseline_12 | 0.0280 | -0.0292 | 5.03 | 945 | KILL_negative_sharpe |
| 17 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s0_20260502T044650Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 18 | `ethusdt_1h_sac_tech_stat_direct_atr_sltp_s1_20260502T054659Z_project3_stage31_firstwave` | ethusdt | 1h | sac | tech_stat | 0.0258 | -0.0554 | 2.44 | 87 | KILL_negative_sharpe |
| 19 | `btcusdt_1h_dqn_baseline_12_direct_atr_sltp_s0_20260502T105233Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | baseline_12 | 0.0231 | -0.0375 | 3.06 | 755 | KILL_negative_sharpe |
| 20 | `btcusdt_4h_sac_tech_full_direct_atr_sltp_s0_20260502T050749Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_full | 0.0157 | -0.0260 | 9.87 | 193 | KILL_negative_sharpe |

## Top 20 By Sharpe

| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave` | ethusdt | 4h | sac | tech_stat | 0.1512 | 0.0115 | 11.11 | 426 | WATCH_preliminary_blocked_until_hardening |
| 2 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260502T043423Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 3 | `btcusdt_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260502T054241Z_project3_stage31_firstwave` | btcusdt | 4h | sac | sota_low_cost | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 4 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T045932Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 5 | `btcusdt_4h_sac_tech_stat_direct_atr_sltp_s1_20260502T054034Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_stat | 0.0814 | -0.0017 | 9.87 | 685 | KILL_negative_sharpe |
| 6 | `btcusdt_4h_ppo_learned_cnn_direct_atr_sltp_s0_20260502T044544Z_project3_stage31_firstwave` | btcusdt | 4h | ppo | learned_cnn | 0.0484 | -0.0176 | 5.00 | 160 | KILL_negative_sharpe |
| 7 | `btcusdt_1h_dqn_tech_full_direct_atr_sltp_s1_20260502T110912Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_full | 0.0379 | -0.0251 | 4.98 | 5 | KILL_negative_sharpe |
| 8 | `btcusdt_15m_dqn_sota_low_cost_direct_atr_sltp_s1_20260502T093842Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | sota_low_cost | 0.0379 | -0.0252 | 4.99 | 128 | KILL_negative_sharpe |
| 9 | `btcusdt_15m_dqn_tech_stat_direct_atr_sltp_s1_20260502T074824Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | tech_stat | 0.0379 | -0.0252 | 4.99 | 128 | KILL_negative_sharpe |
| 10 | `btcusdt_1h_dqn_tech_stat_direct_atr_sltp_s0_20260502T112334Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | tech_stat | 0.0369 | -0.0254 | 4.98 | 40 | KILL_negative_sharpe |
| 11 | `btcusdt_4h_sac_tech_full_direct_atr_sltp_s0_20260502T050749Z_project3_stage31_firstwave` | btcusdt | 4h | sac | tech_full | 0.0157 | -0.0260 | 9.87 | 193 | KILL_negative_sharpe |
| 12 | `btcusdt_15m_dqn_crypto_full_direct_atr_sltp_s1_20260502T100726Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | crypto_full | -0.0212 | -0.0263 | 12.09 | 2148 | KILL_non_positive_return |
| 13 | `btcusdt_15m_dqn_tech_stat_decomp_direct_atr_sltp_s1_20260502T081712Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | tech_stat_decomp | -0.0212 | -0.0263 | 12.09 | 2148 | KILL_non_positive_return |
| 14 | `btcusdt_15m_dqn_tech_full_direct_atr_sltp_s0_20260502T071926Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | tech_full | 0.0313 | -0.0270 | 5.02 | 594 | KILL_negative_sharpe |
| 15 | `btcusdt_4h_dqn_tech_stat_direct_atr_sltp_s0_20260502T050641Z_project3_stage31_firstwave` | btcusdt | 4h | dqn | tech_stat | 0.0310 | -0.0275 | 4.99 | 50 | KILL_negative_sharpe |
| 16 | `btcusdt_15m_dqn_baseline_12_direct_atr_sltp_s0_20260502T065236Z_project3_stage31_firstwave` | btcusdt | 15m | dqn | baseline_12 | 0.0300 | -0.0285 | 5.02 | 621 | KILL_negative_sharpe |
| 17 | `btcusdt_1h_dqn_baseline_12_direct_atr_sltp_s1_20260502T105341Z_project3_stage31_firstwave` | btcusdt | 1h | dqn | baseline_12 | 0.0280 | -0.0292 | 5.03 | 945 | KILL_negative_sharpe |
| 18 | `btcusdt_1h_sac_sota_low_cost_direct_atr_sltp_s0_20260502T184706Z_project3_stage31_firstwave` | btcusdt | 1h | sac | sota_low_cost | 0.0030 | -0.0329 | 9.16 | 587 | KILL_negative_sharpe |
| 19 | `btcusdt_1h_sac_tech_stat_direct_atr_sltp_s0_20260502T111019Z_project3_stage31_firstwave` | btcusdt | 1h | sac | tech_stat | 0.0030 | -0.0329 | 9.16 | 587 | KILL_negative_sharpe |
| 20 | `btcusdt_1h_sac_tech_stat_direct_atr_sltp_s1_20260502T111444Z_project3_stage31_firstwave` | btcusdt | 1h | sac | tech_stat | 0.0030 | -0.0329 | 9.16 | 587 | KILL_negative_sharpe |

## Feature Preset Ranking

| Preset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| sota_low_cost | 10 | 0.0163 | -0.0709 | 4.78 | 6 |
| tech_stat | 77 | 0.0010 | -36.0915 | 1.96 | 24 |
| tech_full | 74 | -0.0061 | -40.2631 | 1.50 | 9 |
| baseline_12 | 72 | -0.0077 | -37.2475 | 1.80 | 14 |
| fx_full | 2 | -0.0126 | -1.0350 | 1.95 | 0 |
| learned_lstm | 30 | -0.0128 | -18.9942 | 2.03 | 3 |
| tech_stat_decomp | 57 | -0.0139 | -39.3454 | 2.10 | 5 |
| learned_cnn | 22 | -0.0155 | -16.7332 | 2.93 | 3 |
| kitchen_sink_guarded | 6 | -0.0167 | -0.8277 | 2.32 | 3 |
| crypto_full | 6 | -0.0524 | -0.1041 | 7.88 | 0 |

## Algorithm Ranking

| Algo | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| sac | 73 | -0.0050 | -0.3715 | 3.74 | 24 |
| dqn | 136 | -0.0079 | -37.6170 | 2.03 | 35 |
| ppo | 147 | -0.0087 | -43.9773 | 1.37 | 8 |

## Asset Ranking

| Asset | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| nzdusd | 16 | -0.0000 | -69.7861 | 0.00 | 4 |
| eurgbp | 16 | -0.0000 | -94.8153 | 0.00 | 5 |
| audusd | 16 | -0.0000 | -68.1501 | 0.01 | 5 |
| usdcad | 16 | -0.0000 | -57.9656 | 0.01 | 1 |
| usdchf | 16 | -0.0000 | -67.3014 | 0.01 | 2 |
| gbpusd | 16 | -0.0001 | -47.6123 | 0.01 | 0 |
| eurusd | 90 | -0.0021 | -55.9113 | 0.30 | 5 |
| usdjpy | 37 | -0.0047 | -0.7201 | 0.81 | 2 |
| ethusdt | 20 | -0.0164 | -0.2833 | 5.11 | 9 |
| btcusdt | 113 | -0.0179 | -0.1788 | 5.22 | 34 |

## Machine Contribution

| Machine | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| omega | 153 | -0.0012 | -52.0140 | 0.34 | 28 |
| gamma | 83 | -0.0033 | -41.7487 | 0.47 | 1 |
| dragon | 120 | -0.0189 | -0.1833 | 5.49 | 38 |

## Promotion Blockers

- All candidates are currently blocked from Stage B promotion by the hardening gate.
- Required before promotion: leakage audit, availability/vintage audit, DSR/PBO-style overfit diagnostics, net-cost sensitivity, and baseline/null comparisons.
- Several high-return runs still show negative Sharpe or low trade counts; those must not be treated as validated edge.

## Deliverables

- `experiments/stage_a_screening/index.csv`
- `experiments/stage_a_screening/stage_a_summary.md`
