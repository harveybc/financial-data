# Project 3 ChatGPT 5.5 Pro Context Packet

Generated: 2026-05-13

Use this as the compact attachment for an external web-only research reviewer.
The reviewer does not have repository access.

## Project Rules

- Project 3 evaluates fixed PPO/SAC/DQN reinforcement-learning trading policies.
- The project varies assets, timeframes, feature/source families, seeds, splits,
  and cost scenarios.
- Stage A was broad screening and is not final tradability evidence.
- Stage B is stricter validation using per-bar/per-step return traces,
  matched baselines, seed checks, cost checks, and statistical gates.
- Stage C is a one-shot heldout firewall using rows at or after `2025-01-01`.
  Stage C must not be used for tuning, repeated evaluation, prompt context, or
  diagnosis.
- Synthetic Phase 4 is training-only. Synthetic-only results are diagnostic and
  cannot prove tradability.
- Do not suggest changing PPO/SAC/DQN algorithms.

## Latest Stage B Pragmatic Run

The pragmatic Stage B queue completed.

| Field | Value |
| --- | ---: |
| Locked configs | 900 |
| Done | 900 |
| Running | 0 |
| Failed | 0 |
| Aborted no-trade | 0 |
| Machines | dragon, gamma, omega |
| Variants | 10 |
| Seeds | 5 |
| Costs | base, plus_50pct, plus_100pct |
| Baselines | no_trade, buy_and_hold, random, momentum, reversal |
| Stage C access | DENIED |

Evidence after syncing remote machine outputs:

| Field | Value |
| --- | ---: |
| Pragmatic evidence files | 900 |
| Total evidence files including legacy | 950 |
| Evidence failures | 0 |
| Evaluator evidence pass/fail | 950 / 0 |

## Finalizer Result

The post-run finalizer ran these workers:

1. `stage_b_run_plan_status_worker.py`
2. `stageb_dsr_pbo_evaluator.py`
3. `stage_b_approval_gate_worker.py`
4. `stage_b_decision_readiness_worker.py`
5. `stage_b_pragmatic_root_cause_worker.py`

All returned code `0`.

Finalizer flags:

| Field | Value |
| --- | --- |
| queue_complete | true |
| analysis_allowed | true |
| training_launched by finalizer | false |
| Stage C touched by finalizer | false |

## Stage B Decision

Stage C remains blocked.

| Field | Value |
| --- | --- |
| Stage C decision | BLOCK_STAGE_C |
| Stage C locked | true |
| Stage B ready candidates | 0 |
| Candidate gates pass/fail | 0 / 322 |
| DSR pass/fail | 0 / 499 |
| Promotion allowed | false |

Hard stop reasons:

- `NO_PASS_STAGE_B_READY_CANDIDATE`
- `NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES`

## Main Blockers

Combined Stage A + Stage B blocker counts:

| Blocker | Count |
| --- | ---: |
| `NON_POSITIVE_RETURN` | 2761 |
| `NO_TRADES` | 1154 |
| `NEGATIVE_SHARPE` | 974 |
| `DSR_RIGOROUS_FAIL` | 343 |
| `FAMILY_REALITY_CHECK_FAIL` | 343 |
| `SEED_UNCERTAINTY_BLOCKED` | 343 |
| `PBO_DEFERRED_OR_FAIL` | 335 |
| `FINAL_EXCESSIVE_TRADES_HARD` | 52 |
| `FINAL_NO_TRADES` | 151 |
| `STAGEB_STAT_EVIDENCE_MISSING` | 23 |
| `ABLATION_FAIL` | 8 |
| `MISSING_COST_SCENARIO` | 4 |
| `BASELINE_FAIL` | 4 |
| `FINAL_ALWAYS_IN_MARKET_LOSING` | 3 |
| `ABLATION_NO_MATCH` | 2 |

Stage B statistical candidate-gate blocker counts:

| Blocker | Count |
| --- | ---: |
| `DSR_RIGOROUS_FAIL` | 322 |
| `FAMILY_REALITY_CHECK_FAIL` | 322 |
| `SEED_UNCERTAINTY_BLOCKED` | 322 |
| `PBO_DEFERRED_OR_FAIL` | 318 |
| `FINAL_EXCESSIVE_TRADES_HARD` | 51 |
| `FINAL_NO_TRADES` | 151 |
| `MISSING_COST_SCENARIO` | 2 |
| `FINAL_ALWAYS_IN_MARKET_LOSING` | 2 |

## Root-Cause Class Summary

| Class | Count | Interpretation |
| --- | ---: | --- |
| economic_failure | 3739 | Many candidates are killed before advanced statistics; do not promote or rerun blindly. |
| trade_behavior_failure | 1360 | Action mapping, exposure, costs, and reward need diagnosis before reruns. |
| statistical_non_significance | 1021 | Stage C promotion blocked; use as exploration signal only. |
| insufficient_repetitions | 343 | Paired seed matrix required. |
| infrastructure_missing | 27 | Missing evidence/cost/baseline artifacts must be repaired before promotion discussion. |
| feature_family_failure | 10 | Feature family redesign or matched ablation evidence required. |

Required questions from the root-cause report:

| Question | Count Signal | Interpretation |
| --- | ---: | --- |
| lose_money_net_of_costs | 3739 | Many candidates are killed by economics; do not promote or rerun blindly. |
| overtrade | 52 | Execution economics hard-block affected traces. |
| always_exposed_losing | 3 | Some policies collapse into static exposure. |
| cost_scenarios_missing | 4 | Operational evidence gap remains for a few groups. |
| seed_count_insufficient | 343 | RL reliability gap; paired seeds required. |
| dsr_raw_blocks | 343 | DSR blocks promotion after multiple-testing correction. |
| baseline_or_family_incomplete | 25 | Some matched baseline/family evidence remains incomplete. |
| pbo_rank_degradation_or_deferred | 335 | Temporal selection stability is not proven. |
| tech_stat_too_broad_or_noisy | 351 | Feature family likely needs split/reduction/regime variants. |

## Trade Behavior

Trace-level behavior summary:

| Metric | Value |
| --- | ---: |
| Rows | 950 |
| No-trade flags | 451 |
| Excessive-trade hard flags | 151 |
| Always-in-market losing flags | 4 |

Important correction: an evaluator bug originally inflated trade counts by
summing cumulative per-split trade counters across train/validation/test. This
was patched on 2026-05-13. After the fix, buy-and-hold is sane at about
`205 trades/year`, and excessive-trade hard flags dropped substantially. The
remaining excessive-trade rows are mostly still above the hard threshold, but
they are no longer the impossible multi-million trades/year artifact.

## Cost Evidence

Pragmatic Stage B used:

- `base`
- `plus_50pct`
- `plus_100pct`

The evaluator was updated to accept either:

- legacy contract: `base + pessimistic`
- pragmatic contract: `base + plus_50pct + plus_100pct`

Some older generated Markdown mentioned legacy `base + pessimistic`; the
root-cause and cost-fragility reports were patched on 2026-05-13 to stop
flagging complete pragmatic cost groups as missing `pessimistic`. Cost-fragility
or missing-cost flags are now `18`, not the earlier stale `307`.

## Current Interpretation

This result does not prove RL cannot trade. It proves no current candidate is
safe to send to Stage C.

The next decision should distinguish:

1. candidates killed by bad economics;
2. candidates killed by no trades;
3. candidates killed by overtrading;
4. candidates killed by static exposure;
5. candidates blocked by missing evidence;
6. candidates with promising raw behavior but failing DSR/PBO/family/seed gates.

## What We Need From ChatGPT 5.5 Pro

We need a skeptical, implementation-grade research memo that tells us what to
do next without violating Stage C.

Focus on:

- diagnosing no-trade vs excessive-trade RL failures;
- deciding whether failures imply environment/action/reward defects or simply
  bad strategy economics;
- whether current feature families are too broad/noisy;
- what feature/source experiments are worth doing next;
- how to prioritize asset/source/feature work under strict multiple-testing
  accounting;
- what should be killed, repaired, rerun, or deferred.

Do not recommend:

- using Stage C for diagnosis;
- repeated Stage C evaluation;
- changing PPO/SAC/DQN algorithms;
- using synthetic-only metrics as tradability evidence.
