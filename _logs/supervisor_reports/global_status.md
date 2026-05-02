# Project 3 Global Status

Generated: 2026-05-02T04:42:44.121703+00:00

## Current Focus

Phase 3.1 Stage A screening is active across Omega, Dragon, and Gamma. Omega is also running the 60-second supervisor loop that relaunches pending queue work when a machine goes idle.

## Machine Status

| Machine | State | Current work-plan task | Expected/generated deliverable |
| --- | --- | --- | --- |
| dragon | running | Stage 3.1 Stage A: `ethusdt_4h_baseline_12_sac_s0_25000` | `_logs/supervisor_reports/stage31_worker_dragon.md`, `experiments/stage_a_screening/runs/dragon/` |
| gamma | running | Stage 3.1 Stage A: `usdjpy_4h_tech_stat_sac_s0_25000` | `_logs/supervisor_reports/stage31_worker_gamma.md`, `experiments/stage_a_screening/runs/gamma/` |
| omega | running | Stage 3.1 Stage A: `ethusdt_1h_baseline_12_dqn_s0_8750` | `_logs/supervisor_reports/stage31_worker_omega.md`, `experiments/stage_a_screening/runs/omega/` |

## Idle Resources

None at this check. Omega, Dragon, and Gamma all have active Stage 3.1 jobs.

## Automation

- Supervisor loop: `_scripts/workers/stage31_supervisor_tick_worker.py --loop --iterations 240 --sleep-seconds 60`.
- Queue merge protection prevents completed jobs from being rerun when work is appended.

## User Blockers

- None right now.
