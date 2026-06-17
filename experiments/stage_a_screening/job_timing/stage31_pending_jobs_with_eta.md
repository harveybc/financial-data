# Stage 3.1 Pending Jobs And ETA

Generated UTC: 2026-06-17T10:22:42.331732+00:00

## Summary

- Pending/active rows tracked: 0
- Historical completed timing samples: 5586
- Estimated wall-clock to drain current active+pending GPU queues: 0.00 hours

| Machine | Active | Pending | Estimated remaining machine-hours |
| --- | ---: | ---: | ---: |
| dragon | 0 | 0 | 0.00 |
| gamma | 0 | 0 | 0.00 |
| omega | 0 | 0 | 0.00 |

## Current Active Jobs

| Machine | Run ID | Asset | TF | Preset | Algo | Seed | Started UTC | Progress | Trades | Profit % | Action non-hold | Deadband | Diagnosis | Source | ETA remaining min | Basis |
| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- |

## Pending Jobs

| # | Machine | Run ID | Asset | TF | Preset | Algo | Seed | Steps | Progress | ETA min | Est start UTC | Est end UTC | Basis |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |

## Output Files

- Pending jobs CSV: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/job_timing/stage31_pending_jobs_with_eta.csv`
- Task progress CSV: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/job_timing/stage31_task_progress.csv`
- Task progress JSON: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/job_timing/stage31_task_progress.json`
- Timing register CSV: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/job_timing/stage31_job_timing_register.csv`

Notes:
- ETAs are medians from completed `training -> complete` ledger pairs.
- `exact_sb3_callback` progress is measured from the PPO/SAC/DQN `model.learn()` callback.
- `elapsed_eta_estimate` progress is used only for already-running jobs that started before callback instrumentation was available.
- Matching priority: exact `(timeframe, preset, algo, timesteps)`, then preset+algo, timeframe+preset, preset, timeframe, global.
- Active job remaining time subtracts elapsed time since the latest ledger active event.
- Pending job start/end estimates are queue-aware and serialized per assigned machine.
