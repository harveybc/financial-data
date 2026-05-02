# Project 3 Tier 2 Context Packet

generated_at: 2026-05-02T19:12:01Z
project_root: /home/harveybc/Documents/GitHub/financial-data
active_stage: Stage 3.1 Stage A screening active; Stage 3.2 Stage A synthesis allowed on Omega CPU when Stage 3.1 local queue is complete; Stage 2 SOTA low-cost enrichment and governance additions are active validation context.
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, Gamma, and the Project 3 event daemon.
supervisor_model_policy: default Hermes/OpenCode provider
experiment_until: none
tier2_model_timeout_seconds: 240
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/20_PHASE_2_OVERVIEW.md; work_plan/24_STAGE_2_4_LEARNED_REPRESENTATIONS.md; work_plan/30_PHASE_3_OVERVIEW.md; work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md; work_plan/SOTA_IMPROVEMENT_SUGGESTIONS.md; work_plan/SOTA_INTEGRATION_DECISIONS.md; work_plan/STAGE_1_3_AGENT_NOTIFICATION_AND_VOICE.md
current_machine_tasks:
- Omega: Stage 3.1 watchdog/service owner, run ledger aggregation, Stage 3.2 Stage A synthesis on CPU when local Stage 3.1 queue is complete, remote output sync, and SOTA governance integration.
- Dragon: Stage 3.1 GPU Stage A screening jobs from ; sync summaries and ledger events back to Omega; report blockers/anomalies via Telegram and event logs.
- Gamma: Stage 3.1 GPU Stage A screening jobs from ; sync summaries and ledger events back to Omega; report blockers/anomalies via Telegram and event logs.
expected_deliverables: experiments/stage_a_screening/runs/<machine>/*/summary.json, experiments/stage_a_screening/index.csv, experiments/stage_a_screening/stage_a_summary.md, artifacts/run_ledger.parquet, artifacts/run_ledger_summary.json, _logs/supervisor_reports/stage31_watchdog.md, _logs/supervisor_reports/stage31_worker_context_packet.md.
relevant_logs: _logs/supervisor_reports/stage31_watchdog.md; _logs/supervisor_reports/stage31_worker_context_packet.md; _logs/supervisor_reports/stage31_supervisor_tick.md; _logs/supervisor_reports/stage31_worker_<machine>.md; _logs/supervisor_reports/global_status.md; _logs/supervisor_reports/project3_event_daemon_events.jsonl.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections. Never mark a deliverable complete from memory or guesswork.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
telegram_event_bus_rule: Telegram is for concise task events only: start, finish, blocker, validation anomaly, idle-with-reason, escalation question, human action needed. Never paste long logs; include deliverable paths and evidence. Omega owns the only bidirectional gateway; remote workers use outbound notification only. Agents must not chatter, debate, or stream routine logs in the group.
deliverable_validation_rule: before declaring task completion, read the exact work-plan task spec and inspect produced deliverables, provenance/docs, acquisition log, and worker logs. If confidence is below 0.8 or the requirement is ambiguous, write a Tier 4/Codex escalation instead of guessing.
