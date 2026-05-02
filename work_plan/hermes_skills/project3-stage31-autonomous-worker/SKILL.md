---
name: project3-stage31-autonomous-worker
description: Use when a Project 3 Hermes worker or supervisor selects, starts, validates, or reports Stage 3.1 Stage A screening jobs without duplicating work.
version: 1.0.0
author: Project 3 Codex/Hermes team
license: MIT
metadata:
  hermes:
    tags: [project3, stage31, rl-screening, autonomous-worker, duplicate-prevention]
    related_skills: [project3-autonomous-supervisor, project3-deliverable-validator, systematic-debugging, subagent-driven-development]
---

# Project 3 Stage 3.1 Autonomous Worker

## Trigger

Use this skill for Project 3 Stage 3.1 Stage A screening when selecting a next run, launching a worker, validating a completed run, reporting progress, or deciding whether a machine is genuinely idle.

## Context First

Start by reading:

1. `/home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports/stage31_worker_context_packet.md`
2. `/home/harveybc/Documents/GitHub/financial-data/work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md`
3. `/home/harveybc/Documents/GitHub/financial-data/work_plan/32_STAGE_3_2_RESULTS_SYNTHESIS.md`
4. `/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_SOTA_CRITIQUE_AND_IMPROVEMENT_PROPOSAL.md`

Correct stale context explicitly. Never assume a stage, deliverable, or queue state from memory.

## Source Of Truth

Use these as authoritative state:

- `experiments/stage_a_screening/queues/<machine>.json`
- `artifacts/run_ledger.parquet`
- `artifacts/run_ledger.jsonl`
- `_metadata/stage31_worker_<machine>.json`
- `_logs/supervisor_reports/stage31_watchdog.json`
- `/tmp/gpu_busy.lock` and live `stage31_agent_multi_run_worker.py` / `seed_sweep.py` processes on each worker host

Telegram is a human-visible event mirror and coordination channel. Do not select work from Telegram text alone. Use the last 10 Telegram-mirrored events in the context packet only to avoid duplicate visible actions and to preserve communication context.

## Before Starting Work

1. Reconcile the queue with `_scripts/workers/stage31_reconcile_queue_worker.py`.
2. Inspect live worker and `seed_sweep.py` processes.
3. Inspect `/tmp/gpu_busy.lock`; remove only stale supervisor-owned locks under the project rules.
4. Confirm the selected run has a runnable status and no matching completed summary.
5. Register or preserve the ledger entry before training starts.
6. Send a concise Telegram event only for start, finish, blocker, validation anomaly, idle-with-reason, escalation, or human action needed.

## Duplicate Prevention

Do not start a run when:

- its `run_id` is already `training`, `running`, `registered`, or `preparing_input`;
- a matching live `seed_sweep.py` process exists;
- a matching `summary.json` already exists;
- the last event context shows another agent started the same `run_id` and the queue has not reconciled yet.

If the evidence conflicts, reconcile first. If it still conflicts, escalate to Codex/Tier 4 with the exact run_id, queue row, process evidence, and deliverable paths.

## Reporting Contract

Every report must include:

- exact work-plan stage: Stage 3.1 Stage A screening;
- machine and model/provider;
- current run_id or idle reason;
- expected deliverable path under `experiments/stage_a_screening/runs/<machine>/`;
- evidence: queue status, PID, lock, summary path, or ledger row;
- next action;
- confidence;
- `context_to_pass_forward`.

Do not declare completion because a process exited. Completion requires queue reconciliation plus a valid run summary and ledger event.

## Escalation

Escalate instead of guessing when:

- the work-plan requirement and produced deliverable do not clearly match;
- the run failed in a way that changes experiment design;
- a Stage B promotion, held-out Stage C, subscription, security, or plan-level decision is involved;
- confidence is below 0.8 after reading the relevant files.
