---
name: project3-realtime-telegram-orchestration
description: Use when Project 3 needs low-latency Telegram/event-bus coordination, real-time worker assignment, idle-machine reduction, or safe use of Hermes/OpenCode/Codex model lanes without relying only on cron.
version: 1.0.0
author: Project 3 Codex/Hermes team
license: MIT
metadata:
  hermes:
    tags: [project3, telegram, realtime-orchestration, event-daemon, idle-dispatch]
    related_skills: [project3-autonomous-supervisor, project3-deliverable-validator, systematic-debugging, subagent-driven-development, opencode, codex]
---

# Project 3 Real-Time Telegram Orchestration

Use Omega as the only bidirectional Telegram gateway owner. Dragon and Gamma must not long-poll the same bot token. They send outbound task events only.

## Operating Model

1. Treat the repo, metadata, logs, and work-plan documents as source of truth.
2. Use `_scripts/orchestration/project3_event_daemon.py` for low-latency deterministic dispatch.
3. Keep cron as a backup heartbeat, not the primary reaction path.
4. Use Telegram for concise events: start, finish, blocker, anomaly, idle-with-reason, escalation question, and human-action-needed.
5. Use Hermes/OpenCode reasoning when a task is ambiguous, blocked, anomalous, or needs plan judgment. Do not spend LLM calls on deterministic dispatch.

## Required Event Fields

Every agent event should include:

- `machine`
- `work_plan_stage`
- `task`
- `status`
- `deliverable_path`
- `validation_evidence`
- `idle_state`
- `recommended_next_action`
- `needs_codex`
- `context_to_pass_forward`

## Real-Time Dispatch Rules

- If a GPU lock is active and the PID exists, do not assign GPU work to that machine.
- If a GPU lock exists but the PID is gone, remove it and record the stale-lock event.
- Before assigning a job, verify the learned-input files or source artifacts exist.
- After a remote job finishes, sync metadata, feature output, and model directory back to Omega.
- If no validated GPU job is ready, assign CPU prep, validation, or Phase 3.1 design work.
- If confidence is below 0.8, write a Codex/Tier 4 escalation instead of guessing.

## Provider Boundary

Allowed unattended lanes:

- Hermes/OpenCode providers already configured for Project 3.
- Ollama local/cloud models configured through supported Hermes providers.
- Official APIs explicitly added to the project runtime environment and budget.

Do not automate consumer ChatGPT or GitHub Copilot web/editor sessions through scraping, hidden browser control, unofficial tokens, or account-sharing workarounds. Use Codex/Copilot manually as Tier 4 tools, or use official API/product surfaces only.

## Telegram Noise Control

Do not paste logs. Include paths and evidence. If many events repeat, summarize and point to `_logs/supervisor_reports/project3_event_daemon_status.md`.
