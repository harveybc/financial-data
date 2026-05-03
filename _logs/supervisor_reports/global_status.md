# Project 3 Global Status

Generated: 2026-05-03T07:24:01Z

## Dispatch Decision

Primary low-latency dispatch is handled by `project3-event-daemon.service`. This cron tick is now a backup heartbeat and Hermes reasoning/checkpoint lane.

Tier 2 should assign work to idle machines as follows:

- Omega: event daemon, sync, local Stage 2.4 GPU jobs when idle, metadata/reporting, Phase 3.1 design readiness, and SOTA integration validation.
- Dragon: Stage 2.4 learned representation GPU jobs for ready slices, then sync to Omega.
- Gamma: Stage 2.4 learned representation GPU jobs plus learned-input prep acceleration, then sync to Omega.
- Stage 1 acquisition/preflight: complete enough for Phase 2/3 progression; legacy repair dispatch is disabled unless explicitly re-enabled.
- Telegram: post only concise events to HermesAgentOrchestration: task start/finish, blocker, anomaly, idle reason, deliverable path, validation evidence, next action, or human action needed.
- Sync: Gamma crypto acceleration syncs to Dragon first, then all completed remote outputs sync back to Omega as canonical root.

Tier 2 must avoid GPU-heavy dispatch when /tmp/gpu_busy.lock exists or VRAM is already occupied.

## Recursive Context Communication

Every Project 3 agent communication must include a compact context packet with stage, task, deliverable, relevant docs/logs, constraints, evidence, anomalies, confidence, improvement suggestion, and context_to_pass_forward.

Deliverable validation rule: read the exact work-plan task spec and inspect the produced artifact before marking complete. If the supervisor is not at least 0.8 confident, escalate to Tier 4/Codex instead of guessing.

## Stage 1.5 Paid Provider Status

# Stage 1.5 Paid Credential Check

Generated: 2026-05-02T00:02:26.940443+00:00

| Provider | Status | Next Action |
| --- | --- | --- |
| FXMacroData | validated | Stage 1.5 FXMacroData acquisition complete; supervisor should use _logs/supervisor_reports/stage15_fxmacrodata_acquisition.md as deliverable evidence. |
| CryptoQuant | validated | Stage 1.5 CryptoQuant acquisition complete; supervisor should use _logs/supervisor_reports/stage15_cryptoquant_acquisition.md as deliverable evidence and preserve the historical-range limitation note. |

# Stage 1.5 FXMacroData Acquisition

Generated: 2026-05-01T23:38:43.553046+00:00

## Summary

- Provider: FXMacroData
- Status: ok
- Calendar rows: 896
- Announcement rows: 18147
- Currencies with calendar: AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY, NZD, PLN, SEK, SGD, USD
- Currencies with announcements: AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY, NZD, PLN, SEK, SGD, USD
- Consensus/forecast columns present: none
- Provider endpoint failures: 19

## Outputs

- `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet`
- `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`

## Notes

- FXMacroData improves no-lookahead macro timing because rows include announcement timestamps.
- It does not currently provide consensus/forecast/surprise fields in the acquired payload, so it does not fully replace Trading Economics or FXStreet Calendar API consensus-surprise data.
- Provider 503/404 endpoint failures are recorded in the JSON summary for supervisor review; successful rows are preserved.

# Stage 1.5 CryptoQuant Acquisition

Generated: 2026-05-02T00:00:28.256107+00:00

## Summary

- Status: ok
- Requested endpoints: 97
- Successful endpoints: 97
- Empty endpoints: 0
- Failed endpoints: 0
- Rows acquired: 9700
- Files: 97
- Groups: btc_exchange_flows, btc_indicators, btc_miner_flows, eth_exchange_flows, eth_indicators, stablecoin_exchange_flows, stablecoin_market, stablecoin_network

## Coverage Note

- Professional API accepted with User-Agent; recent/default daily window returns up to 100 rows per endpoint.
- Explicit older date ranges tested before acquisition returned Out of allowed request range; treat as recent-window coverage unless vendor support confirms historical access/export.

## Deliverable

- `alternative_data/cryptoquant`

# Project 3 Tier 2 Context Packet

generated_at: 2026-05-03T07:24:01Z
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

## Hermes Auto-Improvement

Project-specific skill preload: project3-autonomous-supervisor,project3-stage31-autonomous-worker,project3-realtime-telegram-orchestration,project3-deliverable-validator,systematic-debugging,subagent-driven-development,hermes-agent-skill-authoring

### Omega
```
curator: ENABLED
  runs:           1
  last run:       1d ago
  last summary:   auto: no changes; llm: skipped (no candidates)
  last report:    /home/harveybc/.hermes/logs/curator/20260501-121035
  interval:       every 7d
  stale after:    30d unused
  archive after:  90d unused

agent-created skills: 5 total
  active     5
  stale      0
  archived   0

pinned (3): project3-autonomous-supervisor, project3-deliverable-validator, project3-panel-data-quality-validation

PROJECT3_SKILL_INSTALLED
```

### Dragon
```
[dragon] curator: ENABLED
[dragon]   runs:           1
[dragon]   last run:       1d ago
[dragon]   last summary:   auto: no changes; llm: I will now analyze the candidate skills to identify clusters that should be unified into overarching "umbrella" skills.
[dragon] 
[dragon] ### Analysis of Clusters
[dragon] 
[dragon] 1.  **LLM Training & Optimization Cluster:**
[dragon]     *   `gguf-quantization` (implied by the cont…
[dragon]   last report:    /home/harveybc/.hermes/logs/curator/20260501-114733
[dragon]   interval:       every 7d
[dragon]   stale after:    30d unused
[dragon]   archive after:  90d unused
[dragon] 
[dragon] agent-created skills: 17 total
[dragon]   active     17
[dragon] PROJECT3_SKILL_INSTALLED
```

### Gamma
```
[gamma] curator: ENABLED
[gamma]   runs:           1
[gamma]   last run:       1d ago
[gamma]   last summary:   auto: no changes; llm: skipped (no candidates)
[gamma]   last report:    /home/harveybc/.hermes/logs/curator/20260501-121936
[gamma]   interval:       every 7d
[gamma]   stale after:    30d unused
[gamma]   archive after:  90d unused
[gamma] 
[gamma] agent-created skills: 5 total
[gamma]   active     5
[gamma]   stale      0
[gamma]   archived   0
[gamma] 
[gamma] pinned (3): project3-autonomous-supervisor, project3-deliverable-validator, project3-panel-data-quality-validation
[gamma] 
[gamma] PROJECT3_SKILL_INSTALLED
```

## Autonomous Dispatch

Policy: event daemon detects idle machines every 45 seconds, starts pending safe and non-overlapping Stage 2.4 workers, syncs completed remote outputs back to Omega, and emits concise Telegram events. Cron remains a 12-minute model-reasoning heartbeat.

# Project 3 Event Daemon Status

Generated: 2026-05-03T07:23:31.898631+00:00

## Purpose

Low-latency supervisor loop for Stage 2.4. It syncs remote outputs, detects idle machines, assigns the next validated learned-representation job, and emits concise Telegram events.

- Completed Stage 2.4 learned-representation jobs detected: 40
- Last synced artifacts: 0
- Last assignments: 0

## Machines

| Machine | State | Detail |
| --- | --- | --- |
| omega | supervising | `daemon active; CPU audit/manifest scheduled; no safe light GPU job currently ready` |
| dragon | busy | `agent-multi sac btcusdt_perp 15m tech_stat_decomp seed=0` |
| gamma | busy | `agent-multi sac usdjpy 15m learned_cnn seed=0` |

## Legacy Stage 1 Dispatch

Legacy Stage 1.3 autonomous dispatch is disabled by default. Project 3 event daemon owns active Stage 2.4 low-latency dispatch; set PROJECT3_ENABLE_LEGACY_STAGE1_CRON=1 only for an explicit Stage 1 repair pass.

No Stage 1 report is appended because the legacy dispatcher did not run.

## Stage 1.6 Preflight Dispatch

Policy: legacy Stage 1.6 dispatcher is disabled by default while Stage 2.4/Phase 3.1 are active; re-enable only for an explicit repair pass.

Legacy Stage 1.6 preflight dispatch is disabled by default while Stage 2.4/Phase 3.1 are active. Existing Stage 1.6 reports remain available for audit.

No Stage 1.6 report is appended because the legacy dispatcher did not run.

## Omega
```

┌─────────────────────────────────────────────────────────┐
│                 ⚕ Hermes Agent Status                  │
└─────────────────────────────────────────────────────────┘

◆ Environment
  Project:      /home/harveybc/.hermes/hermes-agent
  Python:       3.11.15
  .env file:    ✓ exists
  Model:        deepseek-v4-pro
  Provider:     OpenCode Go

◆ API Keys
  OpenRouter    ✗ (not set)
  OpenAI        ✗ (not set)
  NVIDIA        ✗ (not set)
  Z.AI/GLM      ✗ (not set)
  Kimi          ✗ (not set)
  StepFun Step Plan  ✗ (not set)
  MiniMax       ✗ (not set)
  MiniMax-CN    ✗ (not set)
  Firecrawl     ✗ (not set)
  Tavily        ✗ (not set)
  Browser Use   ✗ (not set)
  Browserbase   ✗ (not set)
  FAL           ✗ (not set)
  Tinker        ✗ (not set)
  WandB         ✗ (not set)
  ElevenLabs    ✗ (not set)
  GitHub        ✗ (not set)
  Anthropic     ✗ (not set)

◆ Auth Providers
  Nous Portal   ✗ not logged in (run: hermes auth add nous --type oauth)
  OpenAI Codex  ✗ not logged in (run: hermes model)
```

## Dragon
```
[dragon] HOST=dragon
[dragon] CONDA=tensorflow
[dragon] 
[dragon] ┌─────────────────────────────────────────────────────────┐
[dragon] │                 ⚕ Hermes Agent Status                  │
[dragon] └─────────────────────────────────────────────────────────┘
[dragon] 
[dragon] ◆ Environment
[dragon]   Project:      /home/harveybc/.hermes/hermes-agent
[dragon]   Python:       3.11.15
[dragon]   .env file:    ✓ exists
[dragon]   Model:        deepseek-v4-flash:cloud
[dragon]   Provider:     Custom endpoint
[dragon] 
[dragon] ◆ API Keys
[dragon]   OpenRouter    ✗ (not set)
[dragon]   OpenAI        ✗ (not set)
[dragon]   NVIDIA        ✗ (not set)
[dragon]   Z.AI/GLM      ✗ (not set)
[dragon]   Kimi          ✗ (not set)
[dragon]   StepFun Step Plan  ✗ (not set)
[dragon]   MiniMax       ✗ (not set)
[dragon]   MiniMax-CN    ✗ (not set)
[dragon]   Firecrawl     ✗ (not set)
[dragon]   Tavily        ✗ (not set)
[dragon]   Browser Use   ✗ (not set)
[dragon]   Browserbase   ✗ (not set)
[dragon]   FAL           ✗ (not set)
[dragon]   Tinker        ✗ (not set)
[dragon]   WandB         ✗ (not set)
[dragon]   ElevenLabs    ✗ (not set)
[dragon]   GitHub        ✗ (not set)
[dragon]   Anthropic     ✗ (not set)
[dragon] 
[dragon] ◆ Auth Providers
[dragon]   Nous Portal   ✗ not logged in (run: hermes auth add nous --type oauth)
[dragon]   OpenAI Codex  ✗ not logged in (run: hermes model)
[dragon] GPU_LOCK_PRESENT
[dragon] {
[dragon]   "pid": 3784360,
[dragon]   "host": "dragon",
[dragon]   "stage": "3.1",
[dragon]   "command": "agent-multi sac btcusdt_perp 15m tech_stat_decomp seed=0",
[dragon]   "started_at": "2026-05-03T07:20:14.929455+00:00",
[dragon]   "expected_duration_minutes": 180
[dragon] }
[dragon] NVIDIA GeForce RTX 4090 Laptop GPU, 16376 MiB, 393 MiB
```

## Gamma
```
[gamma] HOST=gamma
[gamma] CONDA=tensorflow
[gamma] 
[gamma] ┌─────────────────────────────────────────────────────────┐
[gamma] │                 ⚕ Hermes Agent Status                  │
[gamma] └─────────────────────────────────────────────────────────┘
[gamma] 
[gamma] ◆ Environment
[gamma]   Project:      /home/harveybc/.hermes/hermes-agent
[gamma]   Python:       3.11.15
[gamma]   .env file:    ✓ exists
[gamma]   Model:        deepseek-v4-flash:cloud
[gamma]   Provider:     Custom endpoint
[gamma] 
[gamma] ◆ API Keys
[gamma]   OpenRouter    ✗ (not set)
[gamma]   OpenAI        ✗ (not set)
[gamma]   NVIDIA        ✗ (not set)
[gamma]   Z.AI/GLM      ✗ (not set)
[gamma]   Kimi          ✗ (not set)
[gamma]   StepFun Step Plan  ✗ (not set)
[gamma]   MiniMax       ✗ (not set)
[gamma]   MiniMax-CN    ✗ (not set)
[gamma]   Firecrawl     ✗ (not set)
[gamma]   Tavily        ✗ (not set)
[gamma]   Browser Use   ✗ (not set)
[gamma]   Browserbase   ✗ (not set)
[gamma]   FAL           ✗ (not set)
[gamma]   Tinker        ✗ (not set)
[gamma]   WandB         ✗ (not set)
[gamma]   ElevenLabs    ✗ (not set)
[gamma]   GitHub        ✗ (not set)
[gamma]   Anthropic     ✗ (not set)
[gamma] 
[gamma] ◆ Auth Providers
[gamma]   Nous Portal   ✗ not logged in (run: hermes auth add nous --type oauth)
[gamma]   OpenAI Codex  ✗ not logged in (run: hermes model)
[gamma] GPU_LOCK_PRESENT
[gamma] {
[gamma]   "pid": 3879452,
[gamma]   "host": "gamma",
[gamma]   "stage": "3.1",
[gamma]   "command": "agent-multi sac usdjpy 15m learned_cnn seed=0",
[gamma]   "started_at": "2026-05-03T07:20:09.676279+00:00",
[gamma]   "expected_duration_minutes": 180
[gamma] }
[gamma] NVIDIA GeForce RTX 5070 Ti Laptop GPU, 12227 MiB, 250 MiB
```

## Hermes Tier 2 Note

Model policy: default Hermes/OpenCode provider
Per-model timeout seconds: 240
Here's the honest tick assessment, Coordinator:

**State snapshot (07:24 UTC, 2026-05-03):** Dragon and Gamma are both busy with Stage 3.1 SAC screening (GPU locks fresh, ~170 min remaining each, 48 pending jobs each). Omega is idle with 152 Stage 3.1 jobs completed and 0 pending — its local queue is drained, which per the context packet is the explicit trigger for Stage 3.2 Stage A synthesis on CPU.

**Anomaly detected:** The event daemon shows 40 completed Stage 2.4 learned-representation jobs detected but 0 synced artifacts — those remote outputs from Dragon/Gamma may not be canonical on Omega. Also, the daemon event log is pure maintenance-loop noise (manifest/audit cycles every ~11 minutes, no real task events) for the past ~28 hours, which is benign but noisy.

**Confidence: high** (0.9) — evidence is in `stage31_watchdog.md` (Omega idle, queue 0), `global_status.md` (Stage 3.2 authorized on queue completion), and `project3_event_daemon_status.md` (40 completed, 0 synced).

**Next action:** Dispatch Omega's idle CPU to begin Stage 3.2 Stage A synthesis now — the Stage 3.1 completion gate is met, the context packet explicitly authorizes it, and the 40 unsynced Stage 2.4 artifacts can be queued for the next daemon sync pass without blocking Phase 3 progression.
