# Project 3 Global Status

Generated: 2026-05-02T04:40:15.367273+00:00

## Current Focus

Phase 3.1 Stage A screening is active. The supervisor loop is running on Omega and checks every 60 seconds for idle machines with pending queue work.

## Machine Status

| Machine | State | Current work-plan task | Completed queued jobs | Pending queued jobs | Expected/generated deliverable |
| --- | --- | --- | ---: | ---: | --- |
| dragon | between_ticks | Stage 3.1 Stage A: `see worker report` | 5 | 1 | `_logs/supervisor_reports/stage31_worker_dragon.md`, `experiments/stage_a_screening/runs/dragon/` |
| gamma | running | Stage 3.1 Stage A: `eurusd_1h_learned_lstm_ppo_s0_25000` | 4 | 2 | `_logs/supervisor_reports/stage31_worker_gamma.md`, `experiments/stage_a_screening/runs/gamma/` |
| omega | running | Stage 3.1 Stage A: `eurusd_1h_baseline_12_dqn_s0_8750` | 5 | 1 | `_logs/supervisor_reports/stage31_worker_omega.md`, `experiments/stage_a_screening/runs/omega/` |

## Autonomy

- Active supervisor loop: `_scripts/workers/stage31_supervisor_tick_worker.py --loop --iterations 240 --sleep-seconds 60`.
- Queue repair and merge protection are installed so completed jobs are skipped and externally appended jobs are preserved.
- Dragon/Gamma use `/tmp/gpu_busy.lock`; Omega runs CPU/light jobs to avoid sitting idle while supervising.

## Deliverables Created

- Full Stage A registry: `experiments/stage_a_screening/run_matrix.csv`.
- Machine queues: `experiments/stage_a_screening/queues/{dragon,gamma,omega}.json`.
- Stage 3.1 workers: `_scripts/workers/stage31_prepare_inputs_worker.py`, `stage31_agent_multi_run_worker.py`, `stage31_supervisor_tick_worker.py`.

## User Blockers

- None right now. The next human decision is after enough Stage A summaries are aggregated and the top candidates are visible.
