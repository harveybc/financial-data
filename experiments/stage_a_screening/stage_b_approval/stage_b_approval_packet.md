# Stage B Approval Packet

**Generated at:** 2026-05-14T09:00:44.975508+00:00  
**Heldout firewall:** `2025-01-01`  
**Total candidates:** 4933  
**Stage B ready:** 0  

## Status Summary

| Status | Count |
|--------|-------|
| BLOCKED_BASELINE_COMPARISON | 4 |
| BLOCKED_DSR_DEFERRED | 19 |
| BLOCKED_FAMILY_ABLATION | 8 |
| BLOCKED_MISSING_EVIDENCE | 13 |
| KILL_NEGATIVE_SHARPE | 974 |
| KILL_NON_POSITIVE_RETURN | 2761 |
| KILL_NO_TRADES | 1154 |

## Stage B Ready Candidates

_No candidates are currently Stage B ready._

## Blocker Summary (top 20 by return, non-killed)

| run_slug | status | total_return | blocker_codes |
|----------|--------|-------------|---------------|
| ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave | BLOCKED_DSR_DEFERRED | 0.5294 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;FINAL_ALWAYS_IN_MARKET_LOSING;PBO_DEFERRED_OR_FAIL;SEED_UNCERTAINTY_BLOCKED |
| ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1821 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1821 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1821 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;MISSING_COST_SCENARIO;SEED_UNCERTAINTY_BLOCKED |
| ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave | BLOCKED_DSR_DEFERRED | 0.1821 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED |
| ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1821 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1821 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1750 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260503T192405Z_project3_stage31_firstwave | BLOCKED_DSR_DEFERRED | 0.1675 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED |
| ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s2_20260509T054549Z_project3_stage31_firstwave | BLOCKED_DSR_DEFERRED | 0.1675 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED |
| ethusdt_perp_4h_sac_learned_cnn_direct_atr_sltp_s0_20260503T202932Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1649 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_learned_lstm_direct_atr_sltp_s0_20260503T201607Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1649 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_perp_4h_sac_kitchen_sink_guarded_direct_atr_sltp_s0_20260503T211134Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1588 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1512 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T034628Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1512 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_crypto_full_direct_atr_sltp_s1_20260503T054857Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1463 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_tech_stat_decomp_direct_atr_sltp_s1_20260503T045209Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1463 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_crypto_full_direct_atr_sltp_s2_20260509T035948Z_project3_stage31_firstwave | BLOCKED_FAMILY_ABLATION | 0.1437 | ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_kitchen_sink_guarded_direct_atr_sltp_s2_20260509T032226Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1437 | STAGEB_STAT_EVIDENCE_MISSING |
| ethusdt_4h_sac_tech_full_direct_atr_sltp_s2_20260509T030058Z_project3_stage31_firstwave | BLOCKED_MISSING_EVIDENCE | 0.1437 | DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;MISSING_COST_SCENARIO;SEED_UNCERTAINTY_BLOCKED |

## Governance Gate Policy

Gate configuration: `/home/harveybc/Documents/GitHub/financial-data/experiments/design/stage_b_promotion_gate.yaml`  

Key requirements for `PASS_STAGE_B_READY`:
- Immutable ledger membership
- No heldout data (DATE_TIME >= 2025-01-01) in training inputs
- Beat all simple baselines at base AND pessimistic cost
- Family ablation evidence (PASS or NOT_APPLICABLE)
- Rigorous DSR (Stage A approximation is insufficient)
- PBO/CSCV (always deferred to Stage B with per-step return traces)

> Note: `BLOCKED_DSR_DEFERRED` and `BLOCKED_PBO_DEFERRED` are the expected terminal states for all Stage A candidates. These require Stage B 1M-step runs with `return_trace_file` enabled.
