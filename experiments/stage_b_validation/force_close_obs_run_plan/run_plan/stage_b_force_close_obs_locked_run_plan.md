# Project 3 Stage B Locked Run Plan

Generated UTC: `2026-05-14T03:43:02.712678+00:00`
Plan ID: `stageb_force_close_obs_ethusdt_4h_sac_diagnostic_v1`
Stage C access: `DENIED`
Training launched: `False`
Configs: `90`
Machine assignment counts: `{'dragon': 36, 'gamma': 36, 'omega': 18}`

## Dispatch Rule

minimal force-close observation diagnostic: top ranked ETHUSDT 4h SAC tech_stat_full branch x 5 seeds x 3 costs x candidate+5 baselines; CSV features unchanged, env observation adds force-close context

## Machine Counts

- `dragon`: 36
- `gamma`: 36
- `omega`: 18

## First 30 Jobs

| variant | machine | role | baseline | seed | cost | timesteps |
| --- | --- | --- | --- | ---: | --- | ---: |
| `candidate_tech_stat_full_plus_force_close_obs_s0_base` | dragon | candidate |  | 0 | base | 480000 |
| `baseline_no_trade_tech_stat_full_plus_force_close_obs_s0_base` | gamma | baseline | no_trade | 0 | base | 0 |
| `baseline_buy_and_hold_tech_stat_full_plus_force_close_obs_s0_base` | dragon | baseline | buy_and_hold | 0 | base | 0 |
| `baseline_random_tech_stat_full_plus_force_close_obs_s0_base` | gamma | baseline | random | 0 | base | 0 |
| `baseline_momentum_tech_stat_full_plus_force_close_obs_s0_base` | omega | baseline | momentum | 0 | base | 0 |
| `baseline_reversal_tech_stat_full_plus_force_close_obs_s0_base` | dragon | baseline | reversal | 0 | base | 0 |
| `candidate_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | gamma | candidate |  | 0 | plus_50pct | 480000 |
| `baseline_no_trade_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | dragon | baseline | no_trade | 0 | plus_50pct | 0 |
| `baseline_buy_and_hold_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | gamma | baseline | buy_and_hold | 0 | plus_50pct | 0 |
| `baseline_random_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | omega | baseline | random | 0 | plus_50pct | 0 |
| `baseline_momentum_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | dragon | baseline | momentum | 0 | plus_50pct | 0 |
| `baseline_reversal_tech_stat_full_plus_force_close_obs_s0_plus_50pct` | gamma | baseline | reversal | 0 | plus_50pct | 0 |
| `candidate_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | dragon | candidate |  | 0 | plus_100pct | 480000 |
| `baseline_no_trade_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | gamma | baseline | no_trade | 0 | plus_100pct | 0 |
| `baseline_buy_and_hold_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | omega | baseline | buy_and_hold | 0 | plus_100pct | 0 |
| `baseline_random_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | dragon | baseline | random | 0 | plus_100pct | 0 |
| `baseline_momentum_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | gamma | baseline | momentum | 0 | plus_100pct | 0 |
| `baseline_reversal_tech_stat_full_plus_force_close_obs_s0_plus_100pct` | dragon | baseline | reversal | 0 | plus_100pct | 0 |
| `candidate_tech_stat_full_plus_force_close_obs_s1_base` | gamma | candidate |  | 1 | base | 480000 |
| `baseline_no_trade_tech_stat_full_plus_force_close_obs_s1_base` | omega | baseline | no_trade | 1 | base | 0 |
| `baseline_buy_and_hold_tech_stat_full_plus_force_close_obs_s1_base` | dragon | baseline | buy_and_hold | 1 | base | 0 |
| `baseline_random_tech_stat_full_plus_force_close_obs_s1_base` | gamma | baseline | random | 1 | base | 0 |
| `baseline_momentum_tech_stat_full_plus_force_close_obs_s1_base` | dragon | baseline | momentum | 1 | base | 0 |
| `baseline_reversal_tech_stat_full_plus_force_close_obs_s1_base` | gamma | baseline | reversal | 1 | base | 0 |
| `candidate_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | omega | candidate |  | 1 | plus_50pct | 480000 |
| `baseline_no_trade_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | dragon | baseline | no_trade | 1 | plus_50pct | 0 |
| `baseline_buy_and_hold_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | gamma | baseline | buy_and_hold | 1 | plus_50pct | 0 |
| `baseline_random_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | dragon | baseline | random | 1 | plus_50pct | 0 |
| `baseline_momentum_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | gamma | baseline | momentum | 1 | plus_50pct | 0 |
| `baseline_reversal_tech_stat_full_plus_force_close_obs_s1_plus_50pct` | omega | baseline | reversal | 1 | plus_50pct | 0 |
