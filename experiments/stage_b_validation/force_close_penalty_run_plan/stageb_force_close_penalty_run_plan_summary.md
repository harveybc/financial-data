# Stage B Force-Close Reward-Penalty Run Plan Summary

Generated UTC: `2026-05-14T20:01:14.047094+00:00`

- Stage C access: `DENIED`
- Training launched: `False`
- Variants: `2`
- Penalty coefficients: `[0.0001, 0.0003]`
- Penalty window hours: `4`
- Cost scenarios: `['base', 'plus_50pct', 'plus_100pct']`
- Baselines: `['no_trade', 'buy_and_hold', 'random', 'momentum', 'reversal']`
- Total locked configs: `180`

## Selection Rule

focused force-close reward diagnostic: ETHUSDT 4h SAC tech_stat_full with force-close observation visible plus normalized late-Friday exposure reward penalties; all cells are counted Stage B trials

| variant | penalty coefficient | locked configs | manifest |
| --- | ---: | ---: | --- |
| `tech_stat_full_plus_force_close_obs_penalty_0p0001` | 0.0001 | 90 | `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_penalty_run_plan/plans/tech_stat_full_plus_force_close_obs_penalty_0p0001/stageb_run_plan_manifest.json` |
| `tech_stat_full_plus_force_close_obs_penalty_0p0003` | 0.0003 | 90 | `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_penalty_run_plan/plans/tech_stat_full_plus_force_close_obs_penalty_0p0003/stageb_run_plan_manifest.json` |
