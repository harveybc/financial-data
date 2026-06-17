# Project 3 Weekly Pool Seed Plan

- Schema: `project3_weekly_pool_seed_plan_v2`
- Stage C access: `DENIED`
- Training launched: `false`
- Input: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/inputs/ethusdt/4h/sota_low_cost_plus_event_engineered_v1/train.csv`
- Rows: `8971` from `2019-11-27 16:00:00` to `2023-12-31 20:00:00`
- Early-stop train-tail days: `7`
- Validation days: `7`
- Test days: `7`
- Jobs: `2`
- Subjobs: `16`
- Skipped windows: `0`

## Enqueued Jobs

| job | policy | train years | recent months | subjobs | features |
|---|---|---:|---:|---:|---:|
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_1y` | `scratch_n_years` | 1 |  | 8 | 40 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_start_chain_1y` | `warm_start_chain_n_years` | 1 |  | 8 | 40 |

## Subjobs

| subjob | depends on | train | validation | test | rows |
|---|---|---|---|---|---|
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231218` | `` | `2022-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231211` | `` | `2022-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231204` | `` | `2022-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231127` | `` | `2022-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231120` | `` | `2022-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231113` | `` | `2022-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231106` | `` | `2022-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_scratch_ty1_20231030` | `` | `2022-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231030` | `` | `2022-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231106` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231030` | `2022-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231113` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231106` | `2022-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231120` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231113` | `2022-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231127` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231120` | `2022-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231204` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231127` | `2022-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231211` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231204` | `2022-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 2190/42/42 |
| `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231218` | `ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_warm_ty1_20231211` | `2022-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 2190/42/42 |
