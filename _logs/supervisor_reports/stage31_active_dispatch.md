# Stage 3.1 Active Dispatch

Generated: 2026-05-02T04:26:24.429019+00:00

## Supervisor Decision

Phase 3.1 is active. The first wave starts real RL smoke/screening runs while the full Stage A matrix is registered.

## First-Wave Assignments

| Machine | Stage | Jobs | Expected deliverable |
| --- | --- | --- | --- |
| dragon | 3.1 Stage A first wave | btcusdt 1h baseline_12 ppo s0 25000 steps, ethusdt 1h tech_full ppo s0 25000 steps, btcusdt 4h sota_low_cost sac s0 25000 steps | `_logs/supervisor_reports/stage31_worker_dragon.md` + run summaries |
| gamma | 3.1 Stage A first wave | eurusd 1h baseline_12 ppo s0 25000 steps, usdjpy 1h tech_full ppo s0 25000 steps, eurusd 4h tech_stat_decomp dqn s0 25000 steps | `_logs/supervisor_reports/stage31_worker_gamma.md` + run summaries |
| omega | 3.1 Stage A first wave | btcusdt 4h baseline_12 dqn s0 8750 steps, eurusd 4h baseline_12 ppo s0 8750 steps | `_logs/supervisor_reports/stage31_worker_omega.md` + run summaries |

## Full Stage A Registry

- Registered runs: 432
- Reduced matrix matches the Stage 3.1 design: 4 assets, 2 timeframes, feature-preset sweep, PPO/SAC/DQN, 2 seeds.
- Held-out 2025 data is not used by these first-wave training inputs.
