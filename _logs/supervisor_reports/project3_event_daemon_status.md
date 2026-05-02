# Project 3 Event Daemon Status

Generated: 2026-05-02T19:15:00.095965+00:00

## Purpose

Low-latency supervisor loop for Stage 2.4. It syncs remote outputs, detects idle machines, assigns the next validated learned-representation job, and emits concise Telegram events.

- Completed Stage 2.4 learned-representation jobs detected: 40
- Last synced artifacts: 0
- Last assignments: 1

## Machines

| Machine | State | Detail |
| --- | --- | --- |
| omega | cpu_busy | `audit:stage24_progress` |
| dragon | busy | `agent-multi ppo btcusdt 1h crypto_full seed=1` |
| gamma | busy | `agent-multi dqn eurusd 15m fx_full seed=0` |
