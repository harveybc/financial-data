# Project 3 Stage B Decision Readiness

Generated UTC: `2026-05-14T09:00:37.143568+00:00`
Heldout boundary: `2025-01-01`
Stage C decision: `BLOCK_STAGE_C`
Stage C locked: `True`

## Hard Stop Reasons

- `NO_PASS_STAGE_B_READY_CANDIDATE`
- `NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES`

## Current Counts

- Stage B evidence pass/fail: `1310` / `0`
- Statistical candidate gates pass/fail: `0` / `106`
- DSR pass/fail: `0` / `675`
- Stage B ready candidates: `0`
- Cluster counts: `{'aborted_no_trade': 0, 'done': 90, 'failed': 0, 'not_started': 0, 'running': 0}`
- Next status poll UTC: `2026-05-14T08:54:47.013193+00:00`

## Machine Run-Plan Counts

| Machine | Status Counts |
| --- | --- |
| dragon | `{'DONE': 360}` |
| gamma | `{'DONE': 369}` |
| omega | `{'DONE': 171}` |

## Top Blockers

| Blocker | Count |
| --- | ---: |
| `NON_POSITIVE_RETURN` | 2761 |
| `NO_TRADES` | 1154 |
| `NEGATIVE_SHARPE` | 974 |
| `DSR_RIGOROUS_FAIL` | 127 |
| `FAMILY_REALITY_CHECK_FAIL` | 127 |
| `SEED_UNCERTAINTY_BLOCKED` | 113 |
| `FINAL_NO_TRADES` | 45 |
| `PBO_DEFERRED_OR_FAIL` | 33 |
| `STAGEB_STAT_EVIDENCE_MISSING` | 23 |
| `FINAL_EXCESSIVE_TRADES_HARD` | 16 |
| `ABLATION_FAIL` | 8 |
| `MISSING_COST_SCENARIO` | 4 |
| `BASELINE_FAIL` | 4 |
| `FINAL_ALWAYS_IN_MARKET_LOSING` | 3 |
| `ABLATION_NO_MATCH` | 2 |

## Next Actions

| Blocker | Count | Required Action |
| --- | ---: | --- |
| `NON_POSITIVE_RETURN` | 2761 | Killed by hardening. Do not rerun blindly; only create a new counted trial if a documented parameter/data defect is found. |
| `NO_TRADES` | 1154 | Killed by hardening. Diagnose action deadband/hold-collapse from trace logs before any remediation rerun; no-trade output is not evidence. |
| `NEGATIVE_SHARPE` | 974 | Killed by hardening. Do not promote; investigate only if needed for failure analysis or a new counted trial design. |
| `DSR_RIGOROUS_FAIL` | 127 | Review per-bar net-return traces, N_raw/N_eff policy, skew/kurtosis, and autocorrelation adjustment; candidate cannot advance until rigorous DSR clears. |
| `FAMILY_REALITY_CHECK_FAIL` | 127 | Review matched baseline/family bootstrap tests; raw return is not enough if family-level data-snooping test fails. |
| `SEED_UNCERTAINTY_BLOCKED` | 113 | Provide paired seed evidence, minimum five seeds per candidate/cost scenario, or keep blocked. |
| `FINAL_NO_TRADES` | 45 | Reject or repair no-trade configuration before rerun; do not count no-trade output as useful evidence. |
| `PBO_DEFERRED_OR_FAIL` | 33 | Implement or run purged/embargoed CSCV/PBO evidence; current PBO-lite gate is blocking. |
| `STAGEB_STAT_EVIDENCE_MISSING` | 23 | Produce agent-multi evidence.json and return traces, then re-run the Stage B evaluator. |
| `FINAL_EXCESSIVE_TRADES_HARD` | 16 | Reject or constrain pathological overtrading; hard trade-rate gate exceeded. |
| `ABLATION_FAIL` | 8 | Feature/source family must show marginal value versus matched ablation. |
| `MISSING_COST_SCENARIO` | 4 | Generate both base and pessimistic cost-scenario evidence for the same candidate identity. |

## Top Blocked Candidates

| Candidate | Status | Return | Blockers |
| --- | --- | ---: | --- |
| `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave` | `BLOCKED_DSR_DEFERRED` | 0.529359354815133 | `DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;FINAL_ALWAYS_IN_MARKET_LOSING;PBO_DEFERRED_OR_FAIL;SEED_UNCERTAINTY_BLOCKED` |
| `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s0_20260503T204356Z_project3_stage31_firstwave` | `BLOCKED_FAMILY_ABLATION` | 0.182129791500377 | `ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING` |
| `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s1_20260503T204807Z_project3_stage31_firstwave` | `BLOCKED_FAMILY_ABLATION` | 0.182129791500377 | `ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING` |
| `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | `BLOCKED_MISSING_EVIDENCE` | 0.182129791500377 | `DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;MISSING_COST_SCENARIO;SEED_UNCERTAINTY_BLOCKED` |
| `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | `BLOCKED_DSR_DEFERRED` | 0.182129791500377 | `DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED` |
| `ethusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T060619Z_project3_stage31_firstwave` | `BLOCKED_FAMILY_ABLATION` | 0.182129791500377 | `ABLATION_FAIL;STAGEB_STAT_EVIDENCE_MISSING` |
| `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s2_20260509T055037Z_project3_stage31_firstwave` | `BLOCKED_MISSING_EVIDENCE` | 0.182129791500377 | `STAGEB_STAT_EVIDENCE_MISSING` |
| `ethusdt_perp_4h_sac_tech_full_direct_atr_sltp_s2_20260509T063348Z_project3_stage31_firstwave` | `BLOCKED_MISSING_EVIDENCE` | 0.17502261471533376 | `STAGEB_STAT_EVIDENCE_MISSING` |
| `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260503T192405Z_project3_stage31_firstwave` | `BLOCKED_DSR_DEFERRED` | 0.16745549785451508 | `DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED` |
| `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s2_20260509T054549Z_project3_stage31_firstwave` | `BLOCKED_DSR_DEFERRED` | 0.16745549785451508 | `DSR_RIGOROUS_FAIL;FAMILY_REALITY_CHECK_FAIL;SEED_UNCERTAINTY_BLOCKED` |

## Source Files

- `stageb_stat_report`: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json`
- `approval_packet`: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json`
- `cluster_status`: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/run_plan/stage_b_cluster_live_status.json`
- `run_plan_status`: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/run_plan/stage_b_run_plan_status.json`
- `handoff_spec`: `/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_AGENT_HANDOFF_SPEC_KIT_2026_05_12.md`
