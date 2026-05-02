# Project 3 Agent Notification And Voice

## Purpose

This note documents the Project 3 communication layer for Omega, Dragon, and Gamma Hermes agents. It was introduced during Stage 1.3 and remains active for Stage 1.6 preflight and later stages.

## Telegram Reporting

Project cron wrappers call `_scripts/telegram_notify.py` after Tier 1 and Tier 2 status updates. The helper is safe before setup: it exits without sending anything until Telegram credentials are present.

Telegram is the recommended human-visible management channel because it is fast on mobile, supports group chat, supports bot delivery through a simple API, and is already supported by Hermes. The authoritative project state remains the repo, work-plan documents, logs, `global_status.md`, `project3_event_daemon_status.md`, `project3_event_daemon_events.jsonl`, and `escalation_queue.json`; Telegram is the live notification and coordination surface.

For Stage 2.4 and later, Project 3 uses a hybrid model:

- `_scripts/orchestration/project3_event_daemon.py` is the primary low-latency dispatch loop on Omega.
- `project3-event-daemon.service` runs continuously and checks machine locks/output markers roughly every 45 seconds.
- Cron remains a backup heartbeat and Hermes reasoning/checkpoint lane, not the main reaction path.
- Telegram mirrors important events to the human group, but repo artifacts remain the machine-readable event queue.

Recommended operating model:

- Omega owns the only bidirectional Hermes Telegram gateway for the shared bot token.
- Dragon, Gamma, and Omega workers send outbound structured reports with `_scripts/telegram_notify.py`.
- The Tier 2 supervisor reads worker reports, logs, deliverables, and the work plan before assigning new tasks.
- Workers do not independently debate in the group unless tagged or explicitly delegated by Omega/Tier 2.
- Human questions in the group should mention the bot or use commands; routine worker completion notices do not require mention.
- The group is a low-noise event bus, not a log stream. Agents post starts, finishes, blockers, validation anomalies, idle-with-reason events, escalation questions, deliverable paths, and human-action requests only.
- Codex participates as the Tier 4/frontier coordinator through the repo and Telegram notifier. Codex can send group updates with `_scripts/telegram_notify.py` and can inspect the Hermes gateway state/message store, but the canonical Codex interaction remains the VS Code/Codex session.
- If the gateway is down, Omega restarts it; Dragon/Gamma must not start their own gateway with the same bot token because Telegram long polling would conflict.

Because all Project 3 machines currently share one Telegram bot token, worker-to-supervisor coordination must not depend on the bot reading its own outbound messages. Worker events are written to repo logs/metadata and mirrored to Telegram for humans. If true multi-agent chat over Telegram becomes necessary, use separate bot identities per agent or a dedicated queue backend; otherwise the repo event queue is safer, auditable, and avoids message loops.

Worker completion messages should include:

```text
machine:
work_plan_stage:
task:
status:
deliverable_path:
validation_evidence:
idle_state:
recommended_next_action:
needs_codex:
```

This keeps the group useful for the human and for agents while preventing accidental chatter loops.

When an agent reports completion, it must also tell the supervisor exactly which context the next agent should receive:

```text
context_to_pass_forward:
- project_root:
- active_stage:
- current_task:
- expected_deliverable:
- relevant_docs:
- relevant_logs:
- validation_evidence:
- anomalies:
- confidence:
- suggested_next_action:
```

This recursive context rule prevents each worker from rediscovering the same plan details and makes handoffs auditable.

Required private environment variables:

```bash
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_HOME_CHANNEL=<Telegram group chat id, usually a negative number>
TELEGRAM_HOME_CHANNEL_NAME=HermesAgentOrchestration
```

Optional override:

```bash
PROJECT3_TELEGRAM_CHAT_ID=<chat id for Project 3 reports>
```

Setup flow:

1. Create a Telegram bot with BotFather and keep the token private.
2. Add the bot to the `HermesAgentOrchestration` group.
3. Send any message in the group.
4. Put `TELEGRAM_BOT_TOKEN` in `/home/harveybc/.hermes/.env`.
5. Run `_scripts/telegram_notify.py --discover` from the project root and copy the group chat id into `TELEGRAM_HOME_CHANNEL`.
6. Restart or start Hermes gateway if bidirectional chat control is needed:

```bash
hermes gateway start
```

The notifier sends deduplicated status messages, so unchanged cron ticks do not flood the group.

## Hermes Telegram Gateway

Hermes already includes the `hermes-telegram` toolset and the Telegram platform adapter. Native Telegram interaction is enabled once `TELEGRAM_BOT_TOKEN` is set and the gateway is running. Cron delivery can target `telegram` or `telegram:<chat_id>`.

Run only one long-polling Telegram gateway per bot token. For Project 3, Omega should own the bidirectional Telegram gateway, while Dragon and Gamma should use `_scripts/telegram_notify.py` for outbound status reports. Running the same bot token as a gateway on all three machines would create Telegram polling conflicts.

For group command safety, prefer explicit allowed chats and users after the chat id is known:

```bash
TELEGRAM_GROUP_ALLOWED_CHATS=<group chat id>
TELEGRAM_HOME_CHANNEL=<group chat id>
```

## Voice

Hermes supports CLI and gateway voice features:

- Local STT is configured with `stt.provider: local` and `faster-whisper`.
- Local Piper TTS is installed and verified on Omega, Dragon, and Gamma.
- TTS is currently configured with `tts.provider: piper`.
- Other local TTS providers are supported by Hermes (`neutts`, `kittentts`) but are not required for Stage 1.3 operations.
- `voice.auto_tts` remains `false` so cron workers do not unexpectedly generate audio on every response.

Interactive CLI voice commands:

```text
/voice on
/voice tts
/voice status
/voice off
```

Telegram voice replies are supported by the gateway when a chat enables `/voice tts` or `/voice on`. Telegram voice messages from the user are downloaded for STT transcription by the Telegram adapter.

## Current Recommendation

Use Telegram text notifications first for Project 3 operations. Enable voice replies only for interactive sessions or explicit Telegram `/voice` mode, because routine cron voice updates would add noise and make anomaly triage harder.

Telegram group handling is configured with `telegram.require_mention: true`, `telegram.reactions: true`, and `telegram.free_response_chats` set to the HermesAgentOrchestration chat id. This keeps other group chats mention-gated while allowing normal human Project 3 questions in the orchestration group to reach the Hermes gateway. After the group chat id is known, set `TELEGRAM_GROUP_ALLOWED_CHATS` to that id before enabling the gateway.

## Current Stage Policy

- Stage 1.3 completion-idle capacity is reassigned to Stage 1.6 preflight validation/documentation work.
- Formal Stage 1.6 completion still waits for Stage 1.4 and Stage 1.5 subscription decisions.
- Telegram events for this lane use the same compact report format and must include deliverable paths such as `STAGE_1.6_PREFLIGHT.md`, `INVENTORY.md`, and `_metadata/stage16_preflight_validation_<machine>.json`.
- Stage 2.4 is now the active compute lane. The event daemon assigns learned-representation jobs to Omega/Dragon/Gamma whenever a validated input slice exists and the target GPU is idle.
