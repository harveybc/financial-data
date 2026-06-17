# Stage B No-Pass Root Cause Report

Generated UTC: `2026-05-14T06:16:09.482519+00:00`
Heldout boundary: `2025-01-01`

## Decision

- `stage_c_promotion_allowed`: `false`
- `research_continuation_allowed`: `true`
- `next_action_class`: `diagnose_and_iterate`

## Why No Candidate Passed

| Class | Count | Action |
| --- | ---: | --- |
| `economic_failure` | 3739 | Do not rerun blindly; only create a new counted trial if a documented data/parameter defect exists. |
| `trade_behavior_failure` | 1218 | Diagnose action mapping, exposure, costs, and reward before any rerun. |
| `statistical_non_significance` | 288 | Keep Stage C blocked; use as exploration signal only, not proof. |
| `insufficient_repetitions` | 113 | Run paired seeds or keep blocked; one-off seeds cannot promote. |
| `infrastructure_missing` | 27 | Repair missing evidence/cost scenarios/baseline artifacts before any promotion discussion. |
| `feature_family_failure` | 10 | Redesign or split feature family; require matched ablation evidence. |

## Required Questions

| Question | Count Signal | Interpretation |
| --- | ---: | --- |
| `lose_money_net_of_costs` | 3739 | Many candidates are killed before advanced statistics; do not promote or rerun blindly. |
| `overtrade` | 16 | Execution economics are a hard blocker for affected traces. |
| `always_exposed_losing` | 3 | Policy behavior can collapse into static exposure; diagnose reward/action mapping. |
| `cost_scenarios_missing` | 4 | Operational evidence gap; generate matched costs before promotion. |
| `seed_count_insufficient` | 113 | RL reliability gap; paired seed matrix required. |
| `dsr_raw_blocks` | 127 | Promotion blocked by multiple-testing/statistical filter; exploration may continue. |
| `baseline_or_family_incomplete` | 25 | Matched baseline/evidence coverage is incomplete for some candidates. |
| `pbo_rank_degradation_or_deferred` | 34 | Temporal selection stability is not proven. |
| `tech_stat_too_broad_or_noisy` | 135 | Feature family likely needs split/reduction/regime variants. |

## Top Raw Blockers

| Blocker | Class | Count |
| --- | --- | ---: |
| `NON_POSITIVE_RETURN` | `economic_failure` | 2761 |
| `NO_TRADES` | `trade_behavior_failure` | 1154 |
| `NEGATIVE_SHARPE` | `economic_failure` | 974 |
| `DSR_RIGOROUS_FAIL` | `statistical_non_significance` | 127 |
| `FAMILY_REALITY_CHECK_FAIL` | `statistical_non_significance` | 127 |
| `SEED_UNCERTAINTY_BLOCKED` | `insufficient_repetitions` | 113 |
| `FINAL_NO_TRADES` | `trade_behavior_failure` | 45 |
| `PBO_DEFERRED_OR_FAIL` | `statistical_non_significance` | 34 |
| `STAGEB_STAT_EVIDENCE_MISSING` | `infrastructure_missing` | 23 |
| `FINAL_EXCESSIVE_TRADES_HARD` | `trade_behavior_failure` | 16 |
| `ABLATION_FAIL` | `feature_family_failure` | 8 |
| `BASELINE_FAIL` | `economic_failure` | 4 |
| `MISSING_COST_SCENARIO` | `infrastructure_missing` | 4 |
| `FINAL_ALWAYS_IN_MARKET_LOSING` | `trade_behavior_failure` | 3 |
| `ABLATION_NO_MATCH` | `feature_family_failure` | 2 |

## Trade Behavior Summary

- No-trade trace flags: `635`
- Excessive-trade trace flags: `190`
- Always-in-market losing trace flags: `4`

## Cost Fragility Summary

- Candidate cost groups: `35`
- Missing/fragile current cost evidence groups: `18`

## Recommended Immediate Next Work

1. Do not unlock Stage C.
2. Treat current 0/22 as a Stage C blocker, not a project-kill signal.
3. Implement/emit plus_50pct and plus_100pct cost scenarios for the next targeted matrix.
4. Generate the ETHUSDT 4h SAC pragmatic diagnostic manifest before launching any broad new matrix.
5. Split/reduce `tech_stat` into interpretable subfamilies and regime/OOD variants.
6. Keep every new diagnostic run counted in the multiple-testing ledger.
