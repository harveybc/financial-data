# Stage B Statistical Governance Evaluation

Generated UTC: `2026-05-14T23:00:55.547259+00:00`
Evidence files: `1346`
Evidence pass/fail: `1346` / `0`
DSR pass/fail using N_raw: `0` / `693`
Candidate gates pass/fail: `0` / `118`
Stage C allowed: `False`

## Candidate Gate Blockers

| Blocker | Count |
| --- | ---: |
| DSR_RIGOROUS_FAIL | 118 |
| FAMILY_REALITY_CHECK_FAIL | 118 |
| FINAL_ALWAYS_IN_MARKET_LOSING | 2 |
| FINAL_EXCESSIVE_TRADES_HARD | 17 |
| FINAL_NO_TRADES | 51 |
| MISSING_COST_SCENARIO | 2 |
| PBO_DEFERRED_OR_FAIL | 17 |
| SEED_UNCERTAINTY_BLOCKED | 104 |

## Method Notes

- DSR uses per-bar net returns, skewness, non-excess kurtosis, and both raw/effective trial counts.
- Evidence discovery includes `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/runs`, pragmatic outputs under `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/pragmatic_run_plan/plans`, session-calendar outputs under `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/session_calendar_run_plan/plans`, force-close observation outputs under `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_obs_run_plan/plans`, and force-close penalty outputs under `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_penalty_run_plan/plans`.
- Cost coverage accepts either legacy `['base', 'pessimistic']` or pragmatic `['base', 'plus_100pct', 'plus_50pct']` contracts.
- PBO is contiguous-fold PBO-lite over available traces; full purged retraining CSCV still requires a dedicated Stage B runner.
- White Reality Check / SPA are implemented as deterministic stationary-bootstrap family tests against matched `baseline_12` traces where available.
- Seed uncertainty is fail-closed until at least five paired seeds exist for each candidate/cost scenario.
