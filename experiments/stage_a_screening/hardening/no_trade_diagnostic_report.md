# Stage 3.1 No-Trade Diagnostic Report

Generated UTC: 2026-05-12T21:41:41.674722+00:00
Total Stage A runs: `4933`
No-trade runs: `1154`
Trace scan enabled: `True`
Trace files scanned: `546`
Trace files missing: `608`
Max rows per trace: `0` (`0` means full trace)

## Counts By Algorithm

| Algorithm | No-trade runs |
| --- | ---: |
| dqn | 12 |
| ppo | 533 |
| sac | 609 |

## Counts By Diagnosis

| Diagnosis | Runs |
| --- | ---: |
| missing_summary | 445 |
| needs_continuous_action_trace | 89 |
| needs_discrete_action_trace | 74 |
| policy_deadband_collapse | 340 |
| policy_hold_collapse | 206 |

## Top Required Actions

- Future Stage 3/Stage B runs must emit action diagnostics, trade/profit progress telemetry, and return-trace evidence; no-trade summaries without action telemetry are insufficient.
- Continuous SAC no-trade runs with `policy_deadband_collapse` require a registered threshold/action-scaling diagnostic lane. Any threshold change is a new trial, not a rescue of the original run.
- Discrete PPO/DQN no-trade runs with `policy_hold_collapse` require reward/action-distribution diagnostics before rerun.
- `non_hold_actions_but_no_trades` points to execution guards or broker/fill behavior, not just policy collapse.
- A run with `trades_total == 0` remains a hard kill for promotion until a separately registered diagnostic experiment proves the issue is fixed.

## Sample No-Trade Rows

| Run | Algo | TF | Preset | Trace rows | Non-hold rate | Deadband rate | Diagnosis |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `adausdt_15m_ppo_kitchen_sink_guarded_direct_atr_sltp_s1_20260505T013220Z_project3_stage31_firstwave` | ppo | 15m | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `adausdt_15m_ppo_sota_low_cost_direct_atr_sltp_s1_20260505T004115Z_project3_stage31_firstwave` | ppo | 15m | sota_low_cost | 0 |  |  | missing_summary |
| `adausdt_15m_ppo_tech_stat_direct_atr_sltp_s1_20260504T230005Z_project3_stage31_firstwave` | ppo | 15m | tech_stat | 0 |  |  | missing_summary |
| `adausdt_15m_sac_tech_full_direct_atr_sltp_s0_20260504T221852Z_project3_stage31_firstwave` | sac | 15m | tech_full | 0 |  |  | missing_summary |
| `adausdt_1h_ppo_sota_low_cost_direct_atr_sltp_s1_20260505T032713Z_project3_stage31_firstwave` | ppo | 1h | sota_low_cost | 0 |  |  | missing_summary |
| `adausdt_1h_ppo_tech_stat_direct_atr_sltp_s1_20260505T022413Z_project3_stage31_firstwave` | ppo | 1h | tech_stat | 0 |  |  | missing_summary |
| `adausdt_1h_sac_baseline_12_direct_atr_sltp_s0_20260505T014120Z_project3_stage31_firstwave` | sac | 1h | baseline_12 | 0 |  |  | missing_summary |
| `adausdt_1h_sac_crypto_full_direct_atr_sltp_s2_20260509T115512Z_project3_stage31_firstwave` | sac | 1h | crypto_full | 0 |  |  | missing_summary |
| `adausdt_1h_sac_kitchen_sink_guarded_direct_atr_sltp_s0_20260505T034930Z_project3_stage31_firstwave` | sac | 1h | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `adausdt_1h_sac_learned_cnn_direct_atr_sltp_s0_20260505T030027Z_project3_stage31_firstwave` | sac | 1h | learned_cnn | 0 |  |  | missing_summary |
| `adausdt_1h_sac_learned_lstm_direct_atr_sltp_s0_20260505T024451Z_project3_stage31_firstwave` | sac | 1h | learned_lstm | 0 |  |  | missing_summary |
| `adausdt_1h_sac_sota_low_cost_direct_atr_sltp_s0_20260505T031605Z_project3_stage31_firstwave` | sac | 1h | sota_low_cost | 0 |  |  | missing_summary |
| `adausdt_1h_sac_tech_full_direct_atr_sltp_s0_20260505T015656Z_project3_stage31_firstwave` | sac | 1h | tech_full | 0 |  |  | missing_summary |
| `adausdt_1h_sac_tech_stat_direct_atr_sltp_s0_20260505T021339Z_project3_stage31_firstwave` | sac | 1h | tech_stat | 0 |  |  | missing_summary |
| `adausdt_4h_ppo_kitchen_sink_guarded_direct_atr_sltp_s0_20260505T061208Z_project3_stage31_firstwave` | ppo | 4h | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `adausdt_4h_ppo_sota_low_cost_direct_atr_sltp_s0_20260505T054154Z_project3_stage31_firstwave` | ppo | 4h | sota_low_cost | 0 |  |  | missing_summary |
| `adausdt_4h_ppo_tech_full_direct_atr_sltp_s2_20260509T120412Z_project3_stage31_firstwave` | ppo | 4h | tech_full | 0 |  |  | missing_summary |
| `adausdt_4h_ppo_tech_stat_direct_atr_sltp_s0_20260505T044410Z_project3_stage31_firstwave` | ppo | 4h | tech_stat | 0 |  |  | missing_summary |
| `adausdt_4h_sac_crypto_full_direct_atr_sltp_s0_20260505T054833Z_project3_stage31_firstwave` | sac | 4h | crypto_full | 0 |  |  | missing_summary |
| `adausdt_4h_sac_kitchen_sink_guarded_direct_atr_sltp_s0_20260505T060405Z_project3_stage31_firstwave` | sac | 4h | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `adausdt_4h_sac_learned_cnn_direct_atr_sltp_s0_20260505T051840Z_project3_stage31_firstwave` | sac | 4h | learned_cnn | 0 |  |  | missing_summary |
| `adausdt_4h_sac_learned_lstm_direct_atr_sltp_s0_20260505T050411Z_project3_stage31_firstwave` | sac | 4h | learned_lstm | 0 |  |  | missing_summary |
| `adausdt_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260505T053412Z_project3_stage31_firstwave` | sac | 4h | sota_low_cost | 0 |  |  | missing_summary |
| `adausdt_4h_sac_tech_full_direct_atr_sltp_s0_20260505T042040Z_project3_stage31_firstwave` | sac | 4h | tech_full | 0 |  |  | missing_summary |
| `adausdt_4h_sac_tech_stat_decomp_direct_atr_sltp_s0_20260505T044946Z_project3_stage31_firstwave` | sac | 4h | tech_stat_decomp | 0 |  |  | missing_summary |
| `adausdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260505T043609Z_project3_stage31_firstwave` | sac | 4h | tech_stat | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_crypto_full_direct_atr_sltp_s1_20260504T081808Z_project3_stage31_firstwave` | ppo | 15m | crypto_full | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_kitchen_sink_guarded_direct_atr_sltp_s0_20260504T084220Z_project3_stage31_firstwave` | ppo | 15m | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_kitchen_sink_guarded_direct_atr_sltp_s1_20260504T084555Z_project3_stage31_firstwave` | ppo | 15m | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_sota_low_cost_direct_atr_sltp_s0_20260504T074815Z_project3_stage31_firstwave` | ppo | 15m | sota_low_cost | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_sota_low_cost_direct_atr_sltp_s1_20260504T075216Z_project3_stage31_firstwave` | ppo | 15m | sota_low_cost | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_tech_full_direct_atr_sltp_s0_20260504T053614Z_project3_stage31_firstwave` | ppo | 15m | tech_full | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_tech_stat_decomp_direct_atr_sltp_s1_20260504T063214Z_project3_stage31_firstwave` | ppo | 15m | tech_stat_decomp | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_tech_stat_direct_atr_sltp_s0_20260504T060217Z_project3_stage31_firstwave` | ppo | 15m | tech_stat | 0 |  |  | missing_summary |
| `bnbusdt_15m_ppo_tech_stat_direct_atr_sltp_s1_20260504T060547Z_project3_stage31_firstwave` | ppo | 15m | tech_stat | 0 |  |  | missing_summary |
| `bnbusdt_1h_ppo_baseline_12_direct_atr_sltp_s0_20260504T090411Z_project3_stage31_firstwave` | ppo | 1h | baseline_12 | 0 |  |  | missing_summary |
| `bnbusdt_1h_ppo_kitchen_sink_guarded_direct_atr_sltp_s1_20260504T111211Z_project3_stage31_firstwave` | ppo | 1h | kitchen_sink_guarded | 0 |  |  | missing_summary |
| `bnbusdt_1h_ppo_learned_cnn_direct_atr_sltp_s0_20260504T102336Z_project3_stage31_firstwave` | ppo | 1h | learned_cnn | 0 |  |  | missing_summary |
| `bnbusdt_1h_ppo_learned_lstm_direct_atr_sltp_s0_20260504T100754Z_project3_stage31_firstwave` | ppo | 1h | learned_lstm | 0 |  |  | missing_summary |
| `bnbusdt_1h_ppo_tech_full_direct_atr_sltp_s0_20260504T091903Z_project3_stage31_firstwave` | ppo | 1h | tech_full | 0 |  |  | missing_summary |

## Output Files

- CSV: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/hardening/no_trade_diagnostic_report.csv`
- JSON: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/hardening/no_trade_diagnostic_report.json`
