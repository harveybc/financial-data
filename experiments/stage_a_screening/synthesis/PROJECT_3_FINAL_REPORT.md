# Project 3 Final Report Draft

Generated: 2026-06-04T01:04:03.020637+00:00

## Executive Summary

Stage A and the current Stage B trace audit are complete enough for diagnostic synthesis, but not for promotion. There are zero Stage B-ready candidates. Therefore Stage C must not be launched yet.

## Current Gate State

| Gate | Current result |
| --- | --- |
| Stage A indexed runs | 5669 |
| Stage B ready candidates | 0 |
| DSR pass/fail | 0/693 |
| Return traces found/missing | 1346/0 |
| Run-plan status | {"DONE": 900} |

## Top Raw Stage A Runs

| # | Run | Asset | TF | Algo | Preset | Return | Sharpe | Trades |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | ethusdt_perp | 15m | sac | tech_full | 0.5294 | 0.0699 | 198 |
| 2 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 3 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 4 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260516T053653Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 5 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 166 |
| 6 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 166 |
| 7 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 8 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T102748Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 9 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 166 |
| 10 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260524T104911Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 11 | `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260530T104519Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | sota_low_cost | 0.1821 | 0.0466 | 166 |
| 12 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260524T091707Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_stat | 0.1821 | 0.0466 | 166 |
| 13 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 498 |
| 14 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260530T101542Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 498 |
| 15 | `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s1_20260524T085243Z_project3_stage31_firstwave` | ethusdt_perp | 4h | sac | tech_full | 0.1750 | 0.0311 | 498 |

## Decision

- Stage C launch: **BLOCKED**.
- Correct next work: finish Stage 3.2 diagnostic synthesis, inspect DSR/PBO failures, and decide whether any Stage B rerun design is justified.
- Synthetic Phase 4 remains training-only/protocol-locked and cannot rescue a failed real-data Stage B gate.

## Deliverables Written

experiments/stage_a_screening/synthesis/feature_technique_value_ranking.md
experiments/stage_a_screening/synthesis/data_source_value_ranking.md
experiments/stage_a_screening/synthesis/subscription_cancellation_recommendations.md
experiments/stage_a_screening/synthesis/feature_family_value_ranking.md
experiments/stage_a_screening/synthesis/cost_sensitivity_summary.md
experiments/stage_a_screening/synthesis/baseline_comparison_summary.md
experiments/stage_a_screening/synthesis/leakage_and_availability_audit_summary.md
