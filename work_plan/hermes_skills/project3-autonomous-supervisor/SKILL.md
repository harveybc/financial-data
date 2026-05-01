---
name: project3-autonomous-supervisor
description: Use when supervising Project 3 financial-data workers, reporting machine status, dispatching safe autonomous tasks, or turning repeated acquisition/debugging lessons into reusable Hermes skills.
version: 1.0.0
author: Project 3 Codex/Hermes team
license: MIT
metadata:
  hermes:
    tags: [project3, financial-data, autonomous-supervision, data-acquisition, multi-machine]
    related_skills: [hermes-agent, opencode, codex, systematic-debugging, test-driven-development, subagent-driven-development, hermes-agent-skill-authoring, project3-deliverable-validator]
---

# Project 3 Autonomous Supervisor

## Overview

Project 3 uses `/home/harveybc/Documents/GitHub/financial-data` as the canonical repo and data lake. Omega coordinates, Dragon handles heavy crypto acquisition and later heavy compute, and Gamma handles API-heavy macro/on-chain work. Supervisors must keep useful work moving without waiting for the user when a safe next action is obvious.

The main rule is simple: report clearly, dispatch conservatively, respect GPU locks, and escalate only true blockers. Do not ask the user routine questions. If a task can be safely inferred from the work plan and current logs, execute or recommend the deterministic next action.

Never mark a task or deliverable complete from memory, assumption, or a vague status line. Completion requires deliverable validation against the exact work-plan task spec and produced artifacts. When confidence is below 0.8, or the local model would need to guess what the plan intended, route the question to Tier 4/Codex.

## Machine Roles

| Machine | Role | Current provider/model |
| --- | --- | --- |
| Omega | Canonical repo, Tier 2 orchestration, metadata aggregation, light local workers | OpenCode Go / `deepseek-v4-pro` |
| Dragon | Binance crypto, market-data validation, later GPU-heavy training | Hermes custom Ollama / `deepseek-v4-flash:cloud`, fallback `gemma4:31b-cloud`; local `gemma4:31b` only for offline fallback |
| Gamma | Macro, on-chain, public API acquisition, validation inventory | Hermes custom Ollama / `deepseek-v4-flash:cloud`, fallback `gemma4:31b-cloud`; local `gemma4:31b` only for offline fallback |

Use SSH aliases `dragon` and `gamma`. Non-interactive remote commands should source `.bashrc`, activate the `tensorflow` conda env, and run from the financial-data root.

## Status Report Contract

When asked for status, report every machine with:

- exact work-plan stage;
- agent/model identity;
- busy/idle state;
- reason for that state;
- current task;
- expected or generated deliverable;
- next dispatch or sync action.

Prefer these files as source of truth:

- `_logs/supervisor_reports/global_status.md`
- `_logs/supervisor_reports/autonomous_dispatch_report.md`
- `_logs/supervisor_reports/stage16_preflight_dispatch.md`
- `_logs/supervisor_reports/stage16_quality_validation_<machine>.md`
- `_logs/supervisor_reports/stage16_gamma_quality_warning_classification.md`
- `_logs/supervisor_reports/escalation_queue.json`
- `_logs/<machine>/*worker.log`

## Recursive Context Packet Protocol

Every Project 3 agent communication should carry a compact context packet. This is mandatory for efficient multi-agent work: the receiving agent should not have to rediscover the active stage, machine role, deliverable, or escalation policy from scratch.

Before asking another agent to act, include:

- `project_root`: `/home/harveybc/Documents/GitHub/financial-data`;
- `active_stage`: exact stage name and task id when known;
- `agent_role`: Omega/Dragon/Gamma role and model/provider;
- `current_task`: the concrete worker or validation slice;
- `expected_deliverable`: paths or dataset families expected from the task;
- `relevant_docs`: work-plan docs or deliverable docs the agent should read first;
- `relevant_logs`: exact log/status files to inspect;
- `constraints`: GPU lock rules, idempotency, no destructive cleanup, no routine questions;
- `honesty`: confidence, uncertainties, assumptions, and what evidence supports the claim;
- `anomaly_detection`: suspicious metrics, schema gaps, failed APIs, stale PIDs, silent logs, empty outputs, outlier file counts, or unexpected resource usage;
- `improvement_suggestion`: one reusable workflow, skill candidate, validation check, or orchestration improvement if applicable;
- `context_to_pass_forward`: what the next agent should preserve when communicating onward.

When receiving a context packet, first verify it against local evidence. Correct stale context explicitly. Do not amplify wrong assumptions.

## Honesty And Autocritique

All Project 3 supervisors should be constructively skeptical of their own status claims.

- State confidence as high/medium/low or 0.0-1.0.
- Tie conclusions to evidence: PID, log line, file count, checksum/provenance, or GPU lock.
- Mark uncertainty instead of guessing.
- Suggest one improvement when it would reduce future ambiguity.
- Escalate recurring uncertainty into a validation script or skill candidate.

## Deliverable Validation Discipline

Use `project3-deliverable-validator` whenever checking whether a task is done. The validator must read the corresponding work-plan document first, then inspect the deliverable path(s), provenance/docs, acquisition log rows, and worker logs.

For every deliverable, report:

- exact stage and task id;
- work-plan requirement summary;
- deliverable path(s);
- evidence inspected;
- checks performed;
- status: `validated`, `in_progress`, `partial`, `failed`, or `needs_codex`;
- confidence;
- next action or escalation question.

Do not do mediocre validation. Do not suppose a task is good because a file exists. Do not guess whether a partial free source is "enough" when the work plan asked for more. If the local supervisor is not fully sure, write a Tier 4/Codex item to `_logs/supervisor_reports/escalation_queue.json` so Codex can resolve it at the next status check.

## Anomaly Detection

Look for these issues in every tick:

- worker PID exists but log timestamp is stale;
- log advances but output file count does not;
- output files are empty, tiny, duplicated, or missing provenance;
- remote outputs completed but were not synced to Omega;
- Coin/API errors repeat across multiple assets or series;
- GPU lock is stale, unreadable, or held while no matching process exists;
- VRAM is occupied after supervisor exit;
- produced metrics have impossible values, timestamp gaps, duplicate rows, wrong timezone, or frequency drift.

When an anomaly is detected, include the evidence, severity, likely category, and whether Tier 3 can attempt a bounded fix.

## Autonomous Dispatch Rules

Tier 2 must periodically detect idle resources and assign pending safe work without human intervention.

Safe autonomous actions:

- keep an active worker running;
- start an idempotent pending worker if no matching completion marker exists;
- skip GPU-heavy tasks when `/tmp/gpu_busy.lock` is fresh;
- delete only stale/unreadable supervisor-owned GPU locks according to the work plan;
- sync completed Dragon/Gamma outputs back to Omega;
- write status, inventory, provenance, and acquisition logs.
- after Stage 1.3 completes, reassign completion-idle capacity to Stage 1.6 preflight validation/documentation work without marking formal Stage 1.6 complete before Stage 1.4/1.5 decisions.

Unsafe autonomous actions:

- changing subscriptions or paid-provider decisions;
- broad refactors;
- modifying secrets policy;
- deleting data;
- changing stage gates;
- making final research conclusions.

Those unsafe actions become Tier 4 handoffs.

## Telegram Event Bus Discipline

Telegram is a shared low-noise Project 3 management channel. Use it for concise task events only:

- task started;
- task finished;
- blocker or validation anomaly;
- idle-with-reason;
- escalation question;
- human action needed;
- deliverable path and validation evidence.

Do not paste long logs, stream progress loops, or let workers debate in the group. Omega owns the only bidirectional gateway for the bot token. Dragon and Gamma use outbound `_scripts/telegram_notify.py` only.

## GPU Lock Discipline

Before loading local Gemma or running heavy GPU work on Dragon/Gamma, inspect `/tmp/gpu_busy.lock`.

- Fresh lock: skip or choose CPU/network work.
- Stale lock: log the stale condition, remove it only if it is beyond the allowed age rule, and write an escalation note.
- No lock: a short Hermes supervisor may acquire a five-minute lock and release it on exit.

Acquisition jobs that are network/CPU-bound can continue while GPU VRAM is mostly idle, unless the task itself needs GPU.

## Skill Auto-Improvement

Hermes can improve through reusable skills and the curator. Use this loop:

1. If the same anomaly, source quirk, command pattern, or recovery workflow appears three times, propose a narrow skill.
2. If the workflow is safe, stable, and Project 3-specific, create or update a local skill under `~/.hermes/skills/data-science/`.
3. Keep skills procedural: trigger, diagnosis steps, commands, expected outputs, escalation thresholds.
4. Let `hermes curator` consolidate stale or overlapping agent-created skills. Do not disable curator unless it breaks a running workflow.
5. Pin only critical Project 3 skills that should never be archived.

Do not create skills for one-off failures, secrets, private API key values, or conclusions from unfinished analysis.

## Debugging Discipline

For code bugs, data anomalies, and infra issues:

- use `systematic-debugging`;
- find root cause before patching;
- bound Tier 3 fixes to low/medium/high issues with scope no larger than two files;
- verify with the smallest relevant command;
- route plan/security/subscription/blocker issues to Tier 4.

## Verification Checklist

- [ ] Status names the exact stage and deliverable per agent.
- [ ] Busy/idle reason is grounded in a PID, completion marker, GPU lock, or log line.
- [ ] Deliverable validation read the exact work-plan task spec and inspected the produced artifact.
- [ ] Uncertain or plan-level deliverable questions are escalated to Tier 4/Codex instead of guessed.
- [ ] Remote outputs that finished on Dragon/Gamma are synced or queued for sync.
- [ ] New work is idempotent or explicitly safe to restart.
- [ ] Repeated lessons are captured as skills only when reusable.
- [ ] Curator remains enabled so agent-created skills can be consolidated over time.
