# Stage B Pragmatic Post-Run Finalization

Generated UTC: `2026-05-13T19:31:18.341115+00:00`
Queue complete: `True`
Analysis allowed: `True`
Blocked reason: ``
Training launched by this worker: `False`
Stage C touched by this worker: `False`

## Queue Counts

- Before: `{'assigned': 900, 'done': 900, 'running': 0, 'not_started': 0, 'failed': 0, 'aborted_no_trade': 0, 'cluster_generated_at_utc': '2026-05-13T18:14:09.741031+00:00', 'next_expected_poll_utc': '2026-05-13T18:15:09.741031+00:00', 'all_machine_queries_ok': True}`
- After: `{'assigned': 900, 'done': 900, 'running': 0, 'not_started': 0, 'failed': 0, 'aborted_no_trade': 0, 'cluster_generated_at_utc': '2026-05-13T18:14:09.741031+00:00', 'next_expected_poll_utc': '2026-05-13T18:15:09.741031+00:00', 'all_machine_queries_ok': True}`

## Commands

| Worker | Return Code |
| --- | ---: |
| `stage_b_run_plan_status_worker.py` | `0` |
| `stageb_dsr_pbo_evaluator.py` | `0` |
| `stage_b_approval_gate_worker.py` | `0` |
| `stage_b_decision_readiness_worker.py` | `0` |
| `stage_b_pragmatic_root_cause_worker.py` | `0` |

## Stage B Decision

- Stage C decision: `BLOCK_STAGE_C`
- Stage C locked: `True`
- Approval summary: `{'total_candidates': 4933, 'status_counts': {'BLOCKED_BASELINE_COMPARISON': 4, 'BLOCKED_DSR_DEFERRED': 19, 'BLOCKED_FAMILY_ABLATION': 8, 'BLOCKED_MISSING_EVIDENCE': 13, 'KILL_NEGATIVE_SHARPE': 974, 'KILL_NON_POSITIVE_RETURN': 2761, 'KILL_NO_TRADES': 1154}, 'any_stage_b_ready': False, 'n_stage_b_ready': 0, 'n_with_stageb_stat_gate': 21}`
- Statistical summary: `{'candidate_gate_fail': 322, 'candidate_gate_pass': 0, 'dsr_fail': 499, 'dsr_fail_n_raw': 499, 'dsr_pass': 0, 'dsr_pass_n_raw': 0, 'evidence_fail': 0, 'evidence_files': 950, 'evidence_pass': 950, 'family_test_group_count': 13, 'generated_at_utc': '2026-05-13T19:31:14.803600+00:00', 'pbo_group_count': 6, 'promotion_allowed': False, 'run_count': 950, 'schema_version': 'project3_stageb_statistical_evaluator_v2', 'seed_group_count': 939, 'stage': 'stage_b', 'stage_c_allowed': False, 'stage_c_blocked_reason': 'NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES', 'statistical_governance_status': 'BLOCKED', 'trace_found': 950, 'trace_missing': 0, 'trial_count_for_deflation': 5025, 'trial_count_n_eff': 14, 'trial_count_n_raw': 5025}`
