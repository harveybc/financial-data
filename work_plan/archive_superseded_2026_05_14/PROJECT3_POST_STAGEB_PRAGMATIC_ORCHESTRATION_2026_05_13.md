# Project 3 Post-Stage-B Pragmatic Orchestration

Generated: 2026-05-13

This is the handoff plan for the moment the 900-task Stage B pragmatic queue
finishes. It is designed to prevent idle machines, vague handoffs, and accidental
Stage C access.

## Current Run

Active queue:

- Repository: `/home/harveybc/Documents/GitHub/financial-data`
- Locked plan: `experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.json`
- Live status: `experiments/stage_b_validation/run_plan/stage_b_cluster_live_status.json`
- Plan summary: `experiments/stage_b_validation/pragmatic_run_plan/stageb_pragmatic_run_plan_summary.md`
- Total configs: `900`
- Variants: `10`
- Seeds: `5`
- Costs: `base`, `plus_50pct`, `plus_100pct`
- Baselines: `no_trade`, `buy_and_hold`, `random`, `momentum`, `reversal`
- Stage C access: `DENIED`

Machine assignment:

- dragon: `360`
- gamma: `362`
- omega: `178`

Status rule:

- Every status query must report per machine: current task, done, running,
  pending, progress percent, trades, profit/return, anomaly flags, and next poll
  time.
- No-trade anomaly: non-`no_trade` task at `>=20%` progress and `0` trades.
- Excessive-turnover anomaly is not an execution stop by itself, but is a hard
  Stage B evaluator gate on completed traces.

## Immediate Codex Work Already Added

The evaluator now discovers both legacy and pragmatic evidence:

- legacy: `experiments/stage_b_validation/runs/**/evidence.json`
- pragmatic: `experiments/stage_b_validation/pragmatic_run_plan/plans/**/evidence.json`

The evaluator now recognizes pragmatic cost suffixes:

- `base`
- `plus_50pct`
- `plus_100pct`

Accepted complete cost contracts:

- legacy: `base + pessimistic`
- pragmatic: `base + plus_50pct + plus_100pct`

The post-run finalizer is available:

```bash
cd /home/harveybc/Documents/GitHub/financial-data
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_post_pragmatic_finalizer_worker.py
```

It will not launch training and will not touch Stage C. If the queue is
incomplete, it writes a waiting packet. If the queue is complete, it runs:

1. `stage_b_run_plan_status_worker.py`
2. `stageb_dsr_pbo_evaluator.py`
3. `stage_b_approval_gate_worker.py`
4. `stage_b_decision_readiness_worker.py`
5. `stage_b_pragmatic_root_cause_worker.py`

Outputs:

- `experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.json`
- `experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.md`

## 2026-05-13 Data-Context Gap Addendum

The Friday/session force-close rule is configured in the Stage B run configs,
but the inspected model-ready `tech_stat` data did not include explicit
time-to-Friday or bars-to-force-close features. This is now tracked as a P0 data
context gap.

New artifacts:

- `work_plan/PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md`
- `experiments/stage_b_validation/hardening/data_context_gap_audit.md`
- `experiments/stage_b_validation/hardening/data_context_gap_audit.json`

The Stage B diagnostic input materializer now emits session/calendar variants:

- `baseline_12_plus_session_calendar`
- `tech_stat_full_plus_session_calendar`
- `tech_stat_reduced_corr_v1_plus_session_calendar`

These variants add deterministic timestamp context such as
`calendar_hours_to_friday_close`, `calendar_bars_to_friday_close`,
`calendar_is_friday_force_close_bar`, and `calendar_is_monday_entry_window`.

The paid-source gap is also explicit: CryptoQuant acquisition/shadow-plan
artifacts exist, but the current Stage B pragmatic variants do not yet test a
matched `best_free` versus `best_free_plus_cryptoquant` lane.

## Post-Run Execution Order

When the live status shows:

```text
done = 900
running = 0
not_started = 0
failed = 0
aborted_no_trade = 0
```

do this immediately:

```bash
cd /home/harveybc/Documents/GitHub/financial-data
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_post_pragmatic_finalizer_worker.py
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/tests/test_stageb_dsr_pbo_evaluator.py _scripts/tests/test_stage_b_approval_gate_worker.py -q
/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests -q
```

If any queue item failed or aborted:

1. Do not run Stage C.
2. Run the finalizer anyway with no force; it should refuse analysis.
3. Inspect:
   - `experiments/stage_b_validation/run_plan/stage_b_run_plan_status.md`
   - `experiments/stage_b_validation/run_plan/stage_b_cluster_live_status.md`
   - per-run `agent_multi_stdout.log`
4. Patch infrastructure only if the failure is a deterministic bug.
5. Regenerate a counted rerun packet for only the affected cells.

## Decision Branches

### Branch A: At least one candidate passes all Stage B gates

Do not launch Stage C automatically.

Required first:

1. Freeze the Stage B promotion packet.
2. Freeze exact config, git commits, data hashes, feature hashes, evidence paths.
3. Produce a Stage C launch packet requiring explicit operator approval.
4. Ask for confirmation before the one-shot Stage C evaluation.

### Branch B: No candidate passes, but some candidates have positive net behavior

Run root-cause analysis before more GPU work:

1. Rank candidates by final net return, drawdown, cost fragility, trade rate,
   exposure, seed consistency, and baseline delta.
2. Identify whether failures are:
   - statistical only;
   - economic;
   - overtrading;
   - no-trading;
   - always-in-market;
   - cost-fragile;
   - feature-family weak;
   - baseline dominated.
3. Generate a smaller targeted rerun plan only for candidates with plausible
   economic behavior.

### Branch C: No candidate passes and all plausible candidates are economically bad

Do not continue blind SAC reruns.

Use idle compute on research-safe next experiments:

1. Feature/source diagnostics:
   - mutual information / redundancy / stability analysis;
   - regime-conditioned feature utility;
   - source-family ablation.
2. Asset/timeframe screen:
   - same infrastructure, new candidate hypotheses;
   - every run counted in the ledger.
3. Representation preflight:
   - PCA / autoencoder / contrastive / sequence encoder artifacts trained only
     on training rows;
   - no Stage C access.
4. Synthetic Phase 4 remains training-only and cannot prove tradability.

## Agent Assignments After Queue Completion

### Codex: Integration Owner

Own:

- run the finalizer;
- verify evidence discovery includes all 900 intended cells;
- run evaluator and approval gate;
- produce the final Stage B decision summary;
- decide whether Stage C launch packet is allowed or blocked;
- keep status reporting exact.

Acceptance:

- no Stage C access unless a Stage C packet is explicitly approved later;
- no missing evidence silently ignored;
- current pragmatic cost contract is accepted;
- approval packet and evaluator agree on candidate statuses.

### Claude: Financial-Data Statistical Review

Prompt:

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- /home/harveybc/anaconda3/envs/tensorflow/bin/python

Read first:
1. work_plan/PROJECT3_POST_STAGEB_PRAGMATIC_ORCHESTRATION_2026_05_13.md
2. experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.md
3. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md
4. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json
5. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.md
6. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json
7. experiments/stage_b_validation/hardening/trade_behavior_report.md
8. experiments/stage_b_validation/hardening/cost_fragility_report.md
9. _scripts/workers/stageb_dsr_pbo_evaluator.py
10. _scripts/workers/stage_b_approval_gate_worker.py

Mission:
Review the completed Stage B pragmatic evidence and evaluator output. Do not
make candidates pass by weakening gates. Identify exact economic/statistical
root causes and patch only evaluator/reporting defects.

Hard rules:
- Do not touch Stage C.
- Do not launch training.
- Do not modify PPO/SAC/DQN algorithms.
- Do not weaken DSR/PBO/family/seed/cost/trade gates.

Tasks:
1. Verify the evaluator ingested the expected pragmatic evidence count.
2. Verify base/plus_50pct/plus_100pct costs are grouped under the same candidate.
3. Verify trade gates are computed from final traces, not live progress logs.
4. Verify candidate gates and approval packet agree.
5. Add or patch tests only for real defects.
6. Produce a concise root-cause memo: which variants failed and why.

Commands:
/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stageb_dsr_pbo_evaluator.py _scripts/tests/test_stage_b_approval_gate_worker.py -q
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stageb_dsr_pbo_evaluator.py
/home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_approval_gate_worker.py

Final output:
- files changed;
- commands run;
- evidence count;
- candidate pass/fail counts;
- exact blockers;
- confirmation: no training launched, Stage C untouched.
```

### Copilot: Agent-Multi Infrastructure Review

Prompt:

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi repo.

Repository:
- cd /home/harveybc/Documents/GitHub/agent-multi

Read first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_POST_STAGEB_PRAGMATIC_ORCHESTRATION_2026_05_13.md
2. docs/STAGE_B_EVIDENCE_CONTRACT.md
3. tools/project3_stageb_run_plan.py
4. pipeline_plugins/_return_trace.py
5. pipeline_plugins/rl_pipeline_with_validation.py
6. agent_plugins/buy_hold_agent.py
7. agent_plugins/random_agent.py
8. tests/unit/test_return_trace.py
9. tests/unit/test_project3_stageb_run_plan.py

Mission:
Review the completed pragmatic Stage B run infrastructure and prepare the next
safe run-plan generator if financial-data requests a targeted rerun.

Hard rules:
- Do not launch training.
- Do not unlock Stage C.
- Do not modify PPO/SAC/DQN algorithms.
- Do not weaken trace/evidence guards.

Tasks:
1. Verify every completed run has evidence.json and trace sidecars.
2. Verify cost scenarios and seeds are encoded consistently.
3. Verify deterministic baselines behave as intended:
   - no_trade has zero trades by design;
   - buy_and_hold opens exposure after warmup;
   - random/momentum/reversal are not crashing.
4. If financial-data identifies failed cells, create a dry-run-only rerun plan
   for those exact cells.
5. Add tests for any infrastructure defect found.

Commands:
python -m pytest tests/unit -q
python tools/project3_stageb_run_plan.py --help

Final output:
- files changed;
- tests run;
- evidence path contract;
- rerun-plan status if applicable;
- confirmation: no training launched, Stage C untouched.
```

### ChatGPT 5.5 Pro Web: Research Reviewer

Prompt:

```text
You are an external senior quant/RL research reviewer. You do not have repo
access.

Context:
- Project 3 evaluates fixed PPO/SAC/DQN trading policies.
- Stage B just completed or is completing a pragmatic validation grid:
  10 feature variants, 5 seeds, 3 costs, 5 baselines, 900 configs.
- Stage C is a one-shot 2025-01-01+ heldout firewall and cannot be used for
  tuning.
- Synthetic data is training-only and cannot prove tradability.

Please produce an implementation-grade memo for what to do after Stage B
results are summarized.

Required sections:
1. How to interpret failure cases:
   - no trades;
   - excessive trades;
   - always-in-market losing;
   - baseline dominated;
   - DSR/PBO/family/seed failure.
2. What feature/source experiments are justified next:
   - crypto spot/perps/FX/macro/on-chain/order-flow;
   - technical/statistical/decomposition/learned features;
   - PCA/autoencoder/VAE/contrastive/CNN/LSTM/Transformer representations.
3. What should be done only as research, not promotion evidence.
4. What would violate Stage C discipline.
5. A prioritized GitHub issue checklist.

Do not suggest changing PPO/SAC/DQN algorithms.
Do not suggest Stage C tuning.
Prefer primary papers and official/well-cited references.
```

## GPU Usage After Current Queue

Do not leave GPUs idle after finalization.

If Stage B has a promotable candidate:

- GPUs should remain idle for training until the Stage C launch packet is
  explicitly approved.
- Use coding/research agents for packet verification and documentation.

If Stage B has no promotable candidate but has plausible economic candidates:

- Generate a targeted rerun plan with only repaired or diagnostic cells.
- Use dragon/gamma/omega for that counted Stage B rerun.
- Do not rerun cells killed purely by bad economics unless a concrete
  infrastructure/data defect is found.

If Stage B has no plausible economic candidates:

- Use GPUs for train-only representation/source experiments, each counted in
  the ledger:
  - feature selection/stability;
  - representation pretraining on train rows only;
  - asset/timeframe source screening.

Stage C remains locked in all cases until an explicit Stage C launch packet is
approved.
