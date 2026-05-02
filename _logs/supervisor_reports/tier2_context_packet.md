# Project 3 Tier 2 Context Packet

generated_at: 2026-05-02T07:12:01Z
project_root: /home/harveybc/Documents/GitHub/financial-data
active_stage: Stage 2.4 Learned Representations active; Phase 3.1 experiment design scaffold active; Stage 2 SOTA low-cost enrichment available for validation.
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, Gamma, and the Project 3 event daemon.
supervisor_model_policy: default Hermes/OpenCode provider
experiment_until: none
tier2_model_timeout_seconds: 240
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/20_PHASE_2_OVERVIEW.md; work_plan/24_STAGE_2_4_LEARNED_REPRESENTATIONS.md; work_plan/30_PHASE_3_OVERVIEW.md; work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md; work_plan/SOTA_IMPROVEMENT_SUGGESTIONS.md; work_plan/SOTA_INTEGRATION_DECISIONS.md; work_plan/STAGE_1_3_AGENT_NOTIFICATION_AND_VOICE.md
current_machine_tasks:
- Omega: primary low-latency event-daemon owner; local Stage 2.4 GPU worker when idle; remote output sync; Stage 2.4 metadata audit; Phase 3.1 design readiness; SOTA decision integration.
- Dragon: Stage 2.4 learned representation GPU jobs for ready asset/timeframe slices; sync outputs back to Omega; report blockers/anomalies via Telegram and event logs.
- Gamma: Stage 2.4 learned representation GPU jobs and learned-input prep acceleration; sync outputs back to Omega; report blockers/anomalies via Telegram and event logs.
expected_deliverables: _metadata/stage24_*_autoencoder_<machine>_<asset>_<tf>.json, features/trading_asset_features/<asset>/<tf>/learned_lstm.parquet, features/trading_asset_features/<asset>/<tf>/learned_cnn.parquet, features/learned_models/<asset>/<tf>/*_autoencoder/, _metadata/stage24_learned_input_prep_*.json, _logs/supervisor_reports/project3_event_daemon_status.md, _logs/supervisor_reports/project3_event_daemon_events.jsonl, experiments/design/*.md, work_plan/SOTA_INTEGRATION_DECISIONS.md.
relevant_logs: _logs/supervisor_reports/project3_event_daemon_status.md; _logs/supervisor_reports/project3_event_daemon_events.jsonl; _logs/supervisor_reports/global_status.md; _logs/omega/stage24_*; remote _logs/dragon/stage24_*; remote _logs/gamma/stage24_*.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections. Never mark a deliverable complete from memory or guesswork.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
telegram_event_bus_rule: Telegram is for concise task events only: start, finish, blocker, validation anomaly, idle-with-reason, escalation question, human action needed. Never paste long logs; include deliverable paths and evidence. Omega owns the only bidirectional gateway; remote workers use outbound notification only. Agents must not chatter, debate, or stream routine logs in the group.
deliverable_validation_rule: before declaring task completion, read the exact work-plan task spec and inspect produced deliverables, provenance/docs, acquisition log, and worker logs. If confidence is below 0.8 or the requirement is ambiguous, write a Tier 4/Codex escalation instead of guessing.
