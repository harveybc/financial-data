# Project 3 Stage 1.3 Agent Notification And Voice

## Purpose

This note documents the Stage 1.3 communication layer for Omega, Dragon, and Gamma Hermes agents.

## Telegram Reporting

Project cron wrappers call `_scripts/telegram_notify.py` after Tier 1 and Tier 2 status updates. The helper is safe before setup: it exits without sending anything until Telegram credentials are present.

Telegram is the recommended human-visible management channel for Stage 1.3 because it is fast on mobile, supports group chat, supports bot delivery through a simple API, and is already supported by Hermes. The authoritative project state remains the repo, work-plan documents, logs, `global_status.md`, and `escalation_queue.json`; Telegram is the live notification and coordination surface.

Recommended operating model:

- Omega owns the only bidirectional Hermes Telegram gateway for the shared bot token.
- Dragon, Gamma, and Omega workers send outbound structured reports with `_scripts/telegram_notify.py`.
- The Tier 2 supervisor reads worker reports, logs, deliverables, and the work plan before assigning new tasks.
- Workers do not independently debate in the group unless tagged or explicitly delegated by Omega/Tier 2.
- Human questions in the group should mention the bot or use commands; routine worker completion notices do not require mention.

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

Use Telegram text notifications first for Stage 1.3 operations. Enable voice replies only for interactive sessions or explicit Telegram `/voice` mode, because routine cron voice updates would add noise and make anomaly triage harder.

Telegram group handling is configured with `telegram.require_mention: true` and `telegram.reactions: true`. After the group chat id is known, set `TELEGRAM_GROUP_ALLOWED_CHATS` to that id before enabling the gateway.
