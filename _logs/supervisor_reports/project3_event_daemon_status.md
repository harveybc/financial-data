# Project 3 Event Daemon Status

Generated: 2026-05-02T07:21:12.882576+00:00

## Purpose

Low-latency supervisor loop for Stage 2.4. It syncs remote outputs, detects idle machines, assigns the next validated learned-representation job, and emits concise Telegram events.

- Completed Stage 2.4 learned-representation jobs detected: 40
- Last synced artifacts: 0
- Last assignments: 0

## Machines

| Machine | State | Detail |
| --- | --- | --- |
| omega | supervising | `daemon active; CPU audit/manifest scheduled; no safe light GPU job currently ready` |
| dragon | busy | `agent-multi dqn btcusdt 15m tech_full seed=0` |
| gamma | busy | `agent-multi dqn eurusd 15m baseline_12 seed=2` |
