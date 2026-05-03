# Project 3 Event Daemon Status

Generated: 2026-05-03T07:25:08.624441+00:00

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
