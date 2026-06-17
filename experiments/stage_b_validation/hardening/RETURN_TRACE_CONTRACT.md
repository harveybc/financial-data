# Stage B Return-Trace Evidence Contract

- Accepted evidence schema: `project3_return_trace_evidence_v1`
- Accepted trace schema: `stage_b_return_trace_v1`
- Heldout boundary: `2025-01-01`
- Accepted cost contracts: legacy `['base', 'pessimistic']` or pragmatic `['base', 'plus_100pct', 'plus_50pct']`.
- Evidence roots include `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/runs`, `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/pragmatic_run_plan/plans`, `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/session_calendar_run_plan/plans`, `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_obs_run_plan/plans`, and `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_penalty_run_plan/plans`.
- Each run must write `traces/evidence.json` and one or more trace CSV files.
- Trace SHA-256 in evidence must match the trace file bytes.
- Stage B evaluator refuses any Stage C-authorized trace.
- Candidate promotion requires a complete accepted cost contract, rigorous DSR, PBO-lite, family bootstrap tests, paired seed evidence, and trade-behavior gates.
