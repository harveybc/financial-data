# Project 3 Event Daemon Status

Generated: 2026-05-02T02:43:30.944867+00:00

## Purpose

Low-latency supervisor loop for Stage 2.4. It syncs remote outputs, detects idle machines, assigns the next validated learned-representation job, and emits concise Telegram events.

- Completed Stage 2.4 learned-representation jobs detected: 34
- Last synced artifacts: 1
- Last assignments: 0

## Machines

| Machine | State | Detail |
| --- | --- | --- |
| omega | idle | `no validated ready Stage 2.4 job found` |
| dragon | busy | `_scripts/workers/stage24_lstm_autoencoder_worker.py --machine dragon --asset ethusdt --timeframe 5m --epochs 20 --max-train-windows 24000 --batch-size 128` |
| gamma | busy | `_scripts/workers/stage24_lstm_autoencoder_worker.py --machine gamma --asset btcusdt_perp --timeframe 5m --epochs 20 --max-train-windows 24000 --batch-size 128` |
