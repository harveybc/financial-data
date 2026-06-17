# Project 3 Stage B Summary

Generated UTC: `2026-05-14T06:16:09.483864+00:00`
Heldout boundary: `2025-01-01`

## Decision

- Stage C promotion allowed: `false`
- Research continuation allowed: `true`
- Next action class: `diagnose_and_iterate`

## Statistical Gate Summary

- Evidence pass/fail: `1310` / `0`
- Candidate gates pass/fail: `0` / `106`
- DSR pass/fail: `0` / `675`
- Stage C blocked reason: `NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES`

## Approval Summary

- Total candidates: `4933`
- Stage B ready: `0`
- Status counts: `{'BLOCKED_BASELINE_COMPARISON': 4, 'BLOCKED_DSR_DEFERRED': 19, 'BLOCKED_FAMILY_ABLATION': 8, 'BLOCKED_MISSING_EVIDENCE': 13, 'KILL_NEGATIVE_SHARPE': 974, 'KILL_NON_POSITIVE_RETURN': 2761, 'KILL_NO_TRADES': 1154}`

## Root-Cause Classes

| Class | Count |
| --- | ---: |
| `economic_failure` | 3739 |
| `trade_behavior_failure` | 1218 |
| `statistical_non_significance` | 288 |
| `insufficient_repetitions` | 113 |
| `infrastructure_missing` | 27 |
| `feature_family_failure` | 10 |

## Output Artifacts

- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.csv`
- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.md`
- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/cost_fragility_report.csv`
- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/cost_fragility_report.md`
- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stageb_no_pass_root_cause.md`
- `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/promotion_decision.json`
