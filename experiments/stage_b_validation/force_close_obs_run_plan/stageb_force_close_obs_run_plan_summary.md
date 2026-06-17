# Stage B Force-Close Observation Run Plan Summary

Generated UTC: `2026-05-14T03:43:02.695043+00:00`

- Stage C access: `DENIED`
- Training launched: `False`
- Variants: `1`
- Cost scenarios: `['base', 'plus_50pct', 'plus_100pct']`
- Baselines: `['no_trade', 'buy_and_hold', 'random', 'momentum', 'reversal']`
- Total locked configs: `90`

## Selection Rule

minimal force-close observation diagnostic: top ranked ETHUSDT 4h SAC tech_stat_full branch x 5 seeds x 3 costs x candidate+5 baselines; CSV features unchanged, env observation adds force-close context

| variant | source variant | locked configs | manifest |
| --- | --- | ---: | --- |
| `tech_stat_full_plus_force_close_obs` | `tech_stat_full` | 90 | `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/force_close_obs_run_plan/plans/tech_stat_full_plus_force_close_obs/stageb_run_plan_manifest.json` |
