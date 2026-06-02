# Project 3 Claude/Copilot Post-Stage-B Agent Specs

Generated: 2026-05-13

These are copy-paste-ready specs for the VS Code agents. They are intentionally
explicit about repositories, paths, deliverables, allowed edits, forbidden
actions, and current facts. Do not send the agents a shortened version unless
you also attach this file.

## Current Verified State

Repository with Stage B artifacts:

```text
/home/harveybc/Documents/GitHub/financial-data
```

Agent-multi repository:

```text
/home/harveybc/Documents/GitHub/agent-multi
```

Python for `financial-data`:

```text
/home/harveybc/anaconda3/envs/tensorflow/bin/python
```

The Stage B pragmatic queue completed:

```text
locked configs:          900
done:                    900
running:                 0
failed:                  0
aborted_no_trade:        0
stage_c_access:          DENIED
```

Evidence after syncing dragon/gamma/omega outputs:

```text
pragmatic evidence files:                 900
total evaluator evidence files:           950  # 900 pragmatic + 50 legacy
evidence failures:                        0
```

Post-run finalizer:

```text
_scripts/workers/stage_b_post_pragmatic_finalizer_worker.py
```

Finalizer workers all returned `0`:

1. `stage_b_run_plan_status_worker.py`
2. `stageb_dsr_pbo_evaluator.py`
3. `stage_b_approval_gate_worker.py`
4. `stage_b_decision_readiness_worker.py`
5. `stage_b_pragmatic_root_cause_worker.py`

Current Stage B decision:

```text
Stage C decision:              BLOCK_STAGE_C
Stage C locked:                true
Stage B ready candidates:      0
candidate gates pass/fail:     0 / 322
DSR pass/fail:                 0 / 499
promotion_allowed:             false
```

Top combined blockers:

```text
NON_POSITIVE_RETURN              2761
NO_TRADES                        1154
NEGATIVE_SHARPE                   974
DSR_RIGOROUS_FAIL                 343
FAMILY_REALITY_CHECK_FAIL         343
SEED_UNCERTAINTY_BLOCKED          343
PBO_DEFERRED_OR_FAIL              335
FINAL_EXCESSIVE_TRADES_HARD       152
FINAL_NO_TRADES                   151
STAGEB_STAT_EVIDENCE_MISSING       23
ABLATION_FAIL                       8
MISSING_COST_SCENARIO               4
BASELINE_FAIL                       4
FINAL_ALWAYS_IN_MARKET_LOSING       3
ABLATION_NO_MATCH                   2
```

Known issues to check, not assume fixed:

1. `stage_b_pragmatic_root_cause_worker.py` / cost reports still contain
   legacy `base + pessimistic` assumptions in some places. The current
   pragmatic contract is `base + plus_50pct + plus_100pct`; legacy
   `base + pessimistic` should remain accepted only for old artifacts.
2. `stage_b_approval_gate_worker.py` may not fully reflect the pragmatic
   322-candidate statistical gate universe. Verify whether approval mapping is
   intentionally Stage-A-candidate-only or missing pragmatic candidates.
3. Machine assignment counts should reconcile after sync:
   - locked configs total must be `900`;
   - all machine done counts must sum to `900`;
   - no duplicated or missing evidence should be silently ignored.
4. Trade-rate calculations must be checked from final traces, not live progress
   logs. Excessive trade rates may be real, but trace duration/trade-count
   interpretation must be audited.

---

## Spec A: Claude In `financial-data`

Copy the following prompt into Claude.

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo. You have repository access. You must respond with a final
report even if no code changes are needed. Do not answer "No response requested."

Repository:
cd /home/harveybc/Documents/GitHub/financial-data

Python:
/home/harveybc/anaconda3/envs/tensorflow/bin/python

Project hard rules:
- Stage C is locked. Do not inspect, train, tune, or evaluate any rows at or
  after 2025-01-01.
- Do not launch training.
- Do not modify PPO/SAC/DQN algorithms.
- Do not weaken gates to make candidates pass.
- Treat missing evidence, bad hashes, missing costs, unpaired seeds, or Stage C
  contamination as fail-closed.

Current verified state:
- Stage B pragmatic queue: 900/900 done, 0 running, 0 failed, 0 aborted_no_trade.
- Evidence files: 950 total, 900 pragmatic + 50 legacy, 0 evidence failures.
- Candidate gates: 0 pass / 322 fail.
- DSR: 0 pass / 499 fail.
- Stage C decision: BLOCK_STAGE_C.
- Stage B ready candidates: 0.
- Major blockers: DSR_RIGOROUS_FAIL, FAMILY_REALITY_CHECK_FAIL,
  SEED_UNCERTAINTY_BLOCKED, PBO_DEFERRED_OR_FAIL,
  FINAL_EXCESSIVE_TRADES_HARD, FINAL_NO_TRADES,
  FINAL_ALWAYS_IN_MARKET_LOSING, MISSING_COST_SCENARIO.

Read these files first, in this order:
1. work_plan/PROJECT3_CLAUDE_COPILOT_POST_STAGEB_AGENT_SPECS_2026_05_13.md
2. work_plan/PROJECT3_POST_STAGEB_PRAGMATIC_ORCHESTRATION_2026_05_13.md
3. experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.md
4. experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.json
5. experiments/stage_b_validation/hardening/stage_b_decision_readiness.md
6. experiments/stage_b_validation/hardening/stage_b_decision_readiness.json
7. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md
8. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json
9. experiments/stage_b_validation/hardening/stageb_no_pass_root_cause.md
10. experiments/stage_b_validation/hardening/trade_behavior_report.md
11. experiments/stage_b_validation/hardening/trade_behavior_report.csv
12. experiments/stage_b_validation/hardening/cost_fragility_report.md
13. experiments/stage_b_validation/hardening/cost_fragility_report.csv
14. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.md
15. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json
16. experiments/stage_b_validation/run_plan/stage_b_run_plan_status.md
17. experiments/stage_b_validation/run_plan/stage_b_run_plan_status.json
18. _scripts/workers/stageb_dsr_pbo_evaluator.py
19. _scripts/workers/stage_b_approval_gate_worker.py
20. _scripts/workers/stage_b_pragmatic_root_cause_worker.py
21. _scripts/workers/stage_b_decision_readiness_worker.py
22. _scripts/workers/stage_b_post_pragmatic_finalizer_worker.py
23. _scripts/tests/test_stageb_dsr_pbo_evaluator.py
24. _scripts/tests/test_stage_b_approval_gate_worker.py

Mission:
Turn the completed Stage B pragmatic run into an auditable, actionable decision
package. Your goal is not to make candidates pass. Your goal is to verify that
the final reports are correct, fix reporting/evaluator defects, and produce a
ranked kill/repair/rerun/defer recommendation.

Required checks:

1. Evidence completeness and reconciliation
   - Confirm exactly 900 pragmatic evidence files are discoverable locally.
   - Confirm evaluator sees 950 total evidence files including legacy.
   - Confirm machine done counts sum to 900.
   - Confirm no duplicate evidence path or duplicate run_id silently overwrites
     another run.

2. Cost-contract correctness
   - Current pragmatic contract is: base + plus_50pct + plus_100pct.
   - Legacy contract base + pessimistic may remain accepted for old artifacts.
   - Fix reports that still treat missing pessimistic as a failure for pragmatic
     groups.
   - Add or update tests for this.

3. Trade behavior correctness
   - Verify FINAL_NO_TRADES and FINAL_EXCESSIVE_TRADES_HARD are computed from
     final return traces, not live progress logs.
   - Audit trade-count interpretation:
     if `trades` is cumulative, use the final value; if per-step, sum it.
   - Audit trace-year calculation and split concatenation so trades/year is not
     inflated by a timestamp-span bug.
   - If excessive trades are real, keep the gate. If the report is wrong, fix
     the evaluator/reporting and tests.

4. Approval/evaluator integration
   - Verify `stage_b_approval_gate_worker.py` consumes the latest
     `stageb_dsr_pbo_report.json`.
   - Verify missing statistical gate evidence blocks.
   - Verify no candidate can become PASS_STAGE_B_READY unless every hard gate
     clears.
   - Investigate whether the approval packet's `n_with_stageb_stat_gate=21`
     is expected or stale relative to the evaluator's 322 candidate gates.
     Document exact reason and fix only if it is a real integration defect.

5. Root-cause ranking
   - Produce a ranked table by variant/cost/seed family:
     kill / repair / targeted rerun / defer / research-only.
   - Separate:
     bad economics;
     no-trade behavior;
     overtrading behavior;
     always-in-market losing;
     statistical non-significance;
     missing evidence/infrastructure;
     feature-family weakness.

6. Targeted next-run recommendation
   - Only recommend a rerun if there is a concrete repairable defect or a
     sharply defined diagnostic hypothesis.
   - Every new run must be counted in the ledger/multiple-testing universe.
   - Do not recommend Stage C.

Allowed edits:
- _scripts/workers/stageb_dsr_pbo_evaluator.py
- _scripts/workers/stage_b_approval_gate_worker.py
- _scripts/workers/stage_b_pragmatic_root_cause_worker.py
- _scripts/workers/stage_b_decision_readiness_worker.py
- _scripts/workers/stage_b_post_pragmatic_finalizer_worker.py
- _scripts/tests/test_stageb_dsr_pbo_evaluator.py
- _scripts/tests/test_stage_b_approval_gate_worker.py
- generated hardening/report artifacts under experiments/stage_b_validation/hardening/
- generated approval artifacts under experiments/stage_a_screening/stage_b_approval/
- a short work_plan addendum if needed

Do not edit:
- Stage C data/configs/results.
- agent-multi repo.
- raw data.
- PPO/SAC/DQN algorithm implementations.

Commands to run:
/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stageb_dsr_pbo_evaluator.py _scripts/tests/test_stage_b_approval_gate_worker.py -q
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stageb_dsr_pbo_evaluator.py
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_approval_gate_worker.py
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_decision_readiness_worker.py
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_pragmatic_root_cause_worker.py

Acceptance criteria:
- Tests pass.
- Reports reflect the pragmatic cost contract correctly.
- Evidence counts are reconciled and documented.
- Trade-rate gates are either verified correct or fixed with tests.
- Stage C remains blocked.
- No training launched.
- Final response includes:
  1. files changed;
  2. commands run;
  3. evidence count reconciliation;
  4. candidate pass/fail counts;
  5. exact remaining blockers;
  6. kill/repair/rerun/defer table;
  7. explicit confirmation that Stage C was not touched and no training launched.
```

---

## Spec B: Copilot In `agent-multi`

Copy the following prompt into Copilot.

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi repo. You have repository access. You must respond with a final
report even if no code changes are needed. Do not answer "No response requested."

Primary repository:
cd /home/harveybc/Documents/GitHub/agent-multi

Read-only context repository:
/home/harveybc/Documents/GitHub/financial-data

Project hard rules:
- Do not launch training.
- Do not unlock or inspect Stage C.
- Do not modify PPO/SAC/DQN algorithm implementations.
- Do not weaken return-trace/evidence guards.
- Do not change financial-data outputs directly unless explicitly asked.

Current verified state from financial-data:
- Stage B pragmatic queue: 900/900 done, 0 running, 0 failed, 0 aborted_no_trade.
- Pragmatic evidence files collected locally: 900.
- Total evaluator evidence files: 950 including legacy.
- Candidate gates: 0 pass / 322 fail.
- Stage C decision: BLOCK_STAGE_C.
- Major behavior blockers include FINAL_NO_TRADES and FINAL_EXCESSIVE_TRADES_HARD.

Read these financial-data context files first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_CLAUDE_COPILOT_POST_STAGEB_AGENT_SPECS_2026_05_13.md
2. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_POST_STAGEB_PRAGMATIC_ORCHESTRATION_2026_05_13.md
3. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.md
4. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stage_b_decision_readiness.md
5. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stageb_no_pass_root_cause.md
6. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.md
7. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.csv
8. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/cost_fragility_report.md
9. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/pragmatic_run_plan/stageb_pragmatic_run_plan_summary.md

Then read these agent-multi files:
1. docs/STAGE_B_EVIDENCE_CONTRACT.md
2. tools/project3_stageb_run_plan.py
3. tools/project3_phase4_protocol_dry_run.py
4. pipeline_plugins/_return_trace.py
5. pipeline_plugins/rl_pipeline.py
6. pipeline_plugins/rl_pipeline_with_validation.py
7. agent_plugins/buy_hold_agent.py
8. agent_plugins/random_agent.py
9. agent_plugins/no_trade_agent.py
10. agent_plugins/momentum_agent.py
11. agent_plugins/reversal_agent.py
12. tests/unit/test_return_trace.py
13. tests/unit/test_project3_stageb_run_plan.py

Mission:
Audit whether Stage B trade-behavior failures could be caused by agent-multi
infrastructure rather than bad strategy economics. Patch only real
infrastructure defects. If no defects are found, produce an exact dry-run-only
targeted rerun design recommendation for financial-data/Codex.

Required checks:

1. Evidence contract
   - Confirm `project3_return_trace_evidence_v1` and `stage_b_return_trace_v1`
     are emitted consistently.
   - Confirm trace SHA256 values are byte-level hashes of CSV files.
   - Confirm metadata sidecars and run-level evidence indexes are written for
     train/validation/test where configured.
   - Confirm Stage C guard requires both final_stage_c_evaluation=true and
     stage_c_acknowledged=true.

2. Trade column semantics
   - Determine whether trace column `trades` is cumulative or per-step for:
     no_trade, buy_and_hold, random, momentum, reversal, and SAC pipeline.
   - Confirm the intended interpretation is documented.
   - If mixed semantics exist, fix or document them and add tests.

3. No-trade failures
   - Check whether no-trade outcomes can be caused by:
     warmup blocking the first action;
     action deadband thresholds;
     action shape/type mismatch;
     position update bug;
     cost model blocking entries;
     trace writer dropping trades.
   - `no_trade` baseline is expected to have zero trades; other agents are not.

4. Excessive-trade failures
   - Check whether excessive trades are real or caused by:
     cumulative trade count being recorded every row and later interpreted
     incorrectly;
     duplicated trace rows;
     reset counters across episodes/splits;
     action sampling at every bar without hold/deadband logic;
     random baseline design that is intentionally pathological.
   - Do not weaken financial-data gates. Just verify infrastructure semantics.

5. Baseline behavior
   - no_trade: zero trades by design.
   - buy_and_hold: should open exposure after warmup and then mostly hold.
   - random: may overtrade, but should not crash or emit malformed traces.
   - momentum/reversal: should have deterministic, explainable action changes.

6. Run-plan generation
   - Verify Stage B generated costs are exactly base, plus_50pct, plus_100pct.
   - Verify five seeds are generated.
   - Verify no Stage C access flags are true.
   - Verify configs contain trace/evidence output paths.

Allowed edits:
- docs/STAGE_B_EVIDENCE_CONTRACT.md
- tools/project3_stageb_run_plan.py
- pipeline_plugins/_return_trace.py
- pipeline_plugins/rl_pipeline.py
- pipeline_plugins/rl_pipeline_with_validation.py
- agent_plugins/buy_hold_agent.py
- agent_plugins/random_agent.py
- agent_plugins/no_trade_agent.py
- agent_plugins/momentum_agent.py
- agent_plugins/reversal_agent.py
- tests/unit/test_return_trace.py
- tests/unit/test_project3_stageb_run_plan.py
- new unit tests under tests/unit/

Do not edit:
- PPO/SAC/DQN algorithm implementations.
- financial-data repo.
- Stage C configs/data/results.
- anything that launches training.

Commands to run:
python -m pytest tests/unit -q
python tools/project3_stageb_run_plan.py --help

If you create any dry-run plan command, it must be dry-run only and must not
launch training.

Acceptance criteria:
- Unit tests pass.
- Stage C remains locked.
- No training launched.
- Evidence/trade semantics are either verified correct or patched with tests.
- Final response includes:
  1. files changed;
  2. commands run;
  3. whether no-trade failures are infrastructure bugs or economic/behavioral;
  4. whether excessive-trade failures are infrastructure bugs or expected gate
     failures;
  5. exact recommendation for financial-data targeted rerun, if any;
  6. explicit confirmation that no training launched and Stage C was not touched.
```

