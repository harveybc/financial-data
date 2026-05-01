# Project 3 Tier 2 Context Packet

generated_at: 2026-05-01T22:12:01Z
project_root: /home/harveybc/Documents/GitHub/financial-data
active_stage: Stage 1.3 Free Data Acquisition complete; Stage 1.6 preflight validation active while Stage 1.4/1.5 subscription decisions remain gated.
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, and Gamma.
supervisor_model_policy: default Hermes/OpenCode provider
experiment_until: none
tier2_model_timeout_seconds: 240
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md; work_plan/16_STAGE_1_6_VALIDATION_AND_DOCUMENTATION.md
current_machine_tasks:
- Omega: Stage 1.6 preflight documentation audit, master inventory, acquisition-log/gap aggregation, Stage 1.4 subscription decision handoff, and Stage 1.3 status refresh.
- Dragon: Stage 1.6 preflight and quality validation of market_data outputs, with Stage 1.3 crypto/FINRA workers left completed-idle unless revalidation discovers a real anomaly.
- Gamma: Stage 1.6 preflight and quality validation of macro_economic, alternative_data, reference_data, and economic_calendar outputs, with Stage 1.3 public-source workers left completed-idle unless revalidation discovers a real anomaly.
expected_deliverables: STAGE_1.6_PREFLIGHT.md, INVENTORY.md, audit_documentation_preflight.json, per-machine stage16_preflight_validation_*.json, stage16_quality_validation_*.json, stage16_gamma_quality_warning_classification.json, market_data, macro_economic, alternative_data, reference_data, _metadata/acquisition_log.csv, provenance docs.
relevant_logs: _logs/supervisor_reports/global_status.md; _logs/supervisor_reports/autonomous_dispatch_report.md; _logs/omega; remote _logs/dragon; remote _logs/gamma.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections. Never mark a deliverable complete from memory or guesswork.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
telegram_event_bus_rule: Telegram is for concise task events only: start, finish, blocker, validation anomaly, idle-with-reason, escalation question, human action needed. Never paste long logs; include deliverable paths and evidence. Omega owns the only bidirectional gateway; remote workers use outbound notification only. Agents must not chatter, debate, or stream routine logs in the group.
deliverable_validation_rule: before declaring task completion, read the exact work-plan task spec and inspect produced deliverables, provenance/docs, acquisition log, and worker logs. If confidence is below 0.8 or the requirement is ambiguous, write a Tier 4/Codex escalation instead of guessing.
